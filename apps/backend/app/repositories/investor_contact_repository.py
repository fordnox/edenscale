import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.investor_contact import (
    InvestorContactCreate,
    InvestorContactUpdate,
)


class InvestorContactRepository:
    def __init__(self, db: Session):
        self.db = db

    def _organization_id_for_investor(self, investor_id: uuid.UUID) -> uuid.UUID | None:
        row = (
            self.db.query(Investor.organization_id)
            .filter(Investor.id == investor_id)
            .first()
        )
        return row[0] if row is not None else None

    def _resolve_user_id_by_email(
        self, email: str | None, organization_id: uuid.UUID | None
    ) -> uuid.UUID | None:
        """Match an existing user by email (case-insensitive), but only bind
        when that user already holds a membership in the investor's
        organization — linking anyone else must go through the consent-gated
        invitation flow (see ``link_unclaimed_by_email``)."""
        if not email or organization_id is None:
            return None
        user = (
            self.db.query(User).filter(func.lower(User.email) == email.lower()).first()
        )
        if user is None:
            return None
        has_membership = (
            self.db.query(UserOrganizationMembership.id)
            .filter(
                UserOrganizationMembership.user_id == user.id,
                UserOrganizationMembership.organization_id == organization_id,
            )
            .first()
            is not None
        )
        return user.id if has_membership else None  # type: ignore[return-value]

    def list_for_investor(
        self,
        investor_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[InvestorContact]:
        return (
            self.db.query(InvestorContact)
            .filter(InvestorContact.investor_id == investor_id)
            .order_by(InvestorContact.created_at, InvestorContact.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_for_user_and_investor(
        self,
        investor_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[InvestorContact]:
        return (
            self.db.query(InvestorContact)
            .filter(
                InvestorContact.investor_id == investor_id,
                InvestorContact.user_id == user_id,
            )
            .order_by(InvestorContact.created_at, InvestorContact.id)
            .all()
        )

    def get(self, contact_id: uuid.UUID) -> InvestorContact | None:
        return (
            self.db.query(InvestorContact)
            .filter(InvestorContact.id == contact_id)
            .first()
        )

    def _clear_other_primaries(
        self, investor_id: uuid.UUID, except_contact_id: uuid.UUID | None
    ) -> None:
        query = self.db.query(InvestorContact).filter(
            InvestorContact.investor_id == investor_id,
            InvestorContact.is_primary.is_(True),
        )
        if except_contact_id is not None:
            query = query.filter(InvestorContact.id != except_contact_id)
        for sibling in query.all():
            sibling.is_primary = False

    def create(
        self, investor_id: uuid.UUID, data: InvestorContactCreate
    ) -> InvestorContact:
        payload = data.model_dump()
        is_primary = bool(payload.get("is_primary"))
        if payload.get("user_id") is None:
            payload["user_id"] = self._resolve_user_id_by_email(
                payload.get("email"),
                self._organization_id_for_investor(investor_id),
            )
        contact = InvestorContact(investor_id=investor_id, **payload)
        self.db.add(contact)
        self.db.flush()
        if is_primary:
            self._clear_other_primaries(
                investor_id,
                except_contact_id=contact.id,  # type: ignore[invalid-argument-type]
            )
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def update(
        self, contact_id: uuid.UUID, data: InvestorContactUpdate
    ) -> InvestorContact | None:
        contact = self.get(contact_id)
        if contact is None:
            return None
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(contact, key, value)
        if contact.user_id is None and "user_id" not in updates:
            contact.user_id = self._resolve_user_id_by_email(
                contact.email,  # type: ignore[invalid-argument-type]
                self._organization_id_for_investor(contact.investor_id),  # type: ignore[invalid-argument-type]
            )
        if updates.get("is_primary") is True:
            self._clear_other_primaries(
                contact.investor_id, except_contact_id=contact.id  # type: ignore[invalid-argument-type]
            )
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def delete(self, contact_id: uuid.UUID) -> InvestorContact | None:
        contact = self.get(contact_id)
        if contact is None:
            return None
        self.db.delete(contact)
        self.db.commit()
        return contact

    def investor_organizations_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        """Organizations the user has investor-portal access to — i.e. every
        org containing at least one contact linked to them. This, not
        membership, is what grants access to the investor portal."""
        return (
            self.db.query(Organization)
            .join(Investor, Investor.organization_id == Organization.id)
            .join(InvestorContact, InvestorContact.investor_id == Investor.id)
            .filter(InvestorContact.user_id == user_id)
            .distinct()
            .order_by(Organization.name)
            .all()
        )

    def user_has_links_in_organization(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> bool:
        """True when the user is a linked contact of any investor in the org."""
        return (
            self.db.query(InvestorContact.id)
            .join(Investor, Investor.id == InvestorContact.investor_id)
            .filter(
                InvestorContact.user_id == user_id,
                Investor.organization_id == organization_id,
            )
            .first()
            is not None
        )

    def link_unclaimed_by_email(
        self, organization_id: uuid.UUID, email: str, user_id: uuid.UUID
    ) -> list[InvestorContact]:
        """Bind user_id to any contact in this org matching email that has none yet."""
        contacts = (
            self.db.query(InvestorContact)
            .join(Investor, Investor.id == InvestorContact.investor_id)
            .filter(
                Investor.organization_id == organization_id,
                InvestorContact.user_id.is_(None),
                func.lower(InvestorContact.email) == email.lower(),
            )
            .all()
        )
        for contact in contacts:
            contact.user_id = user_id
        if contacts:
            self.db.commit()
        return contacts
