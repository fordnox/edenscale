import uuid

from sqlalchemy.orm import Session

from app.models.investor_contact import InvestorContact
from app.schemas.investor_contact import (
    InvestorContactCreate,
    InvestorContactUpdate,
)


class InvestorContactRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_investor(
        self,
        investor_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[InvestorContact]:
        return (
            self.db.query(InvestorContact)
            .filter(InvestorContact.investor_id == investor_id)
            .order_by(InvestorContact.id)
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
            .order_by(InvestorContact.id)
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
