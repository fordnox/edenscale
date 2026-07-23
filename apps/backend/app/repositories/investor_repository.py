import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.models.commitment import Commitment
from app.models.enums import UserRole
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.lp_scope import lp_visible_investor_ids
from app.schemas.investor import InvestorCreate, InvestorUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager)


class InvestorRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self, organization_id: uuid.UUID | None = None) -> Query:
        sub_query = self.db.query(
            Commitment.investor_id.label("investor_id"),
            func.coalesce(func.sum(Commitment.committed_amount), 0).label(
                "total_committed"
            ),
            func.count(func.distinct(Commitment.fund_id)).label("fund_count"),
        )
        if organization_id is not None:
            # Scope the aggregate to the tenant inside the subquery so the
            # planner isn't grouping every commitment row on the platform
            # before the outer query discards the rest. Results are
            # unchanged: the outer query still filters on organization_id.
            sub_query = sub_query.join(
                Investor, Investor.id == Commitment.investor_id
            ).filter(Investor.organization_id == organization_id)
        sub = sub_query.group_by(Commitment.investor_id).subquery()
        return self.db.query(
            Investor,
            func.coalesce(sub.c.total_committed, 0).label("total_committed"),
            func.coalesce(sub.c.fund_count, 0).label("fund_count"),
        ).outerjoin(sub, sub.c.investor_id == Investor.id)

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        skip: int = 0,
        limit: int = 100,
    ) -> list[tuple[Investor, Decimal, int]]:
        query = self._base_query(membership.organization_id).filter(  # type: ignore[invalid-argument-type]
            Investor.organization_id == membership.organization_id
        )
        if membership.role not in _ORG_VISIBLE_ROLES:
            query = query.filter(Investor.id.in_(lp_visible_investor_ids(membership)))
        return (
            query.order_by(Investor.created_at, Investor.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def primary_contacts_for(
        self, investor_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, InvestorContact]:
        """Map investor id -> its primary contact, in one query for the page.

        `is_primary` is a nullable flag with no uniqueness constraint, so an
        investor can end up with more than one flagged; ties break on
        created_at/id to keep the register stable between requests. Investors
        with no flagged contact are simply absent from the map.
        """
        if not investor_ids:
            return {}
        rows = (
            self.db.query(InvestorContact)
            .filter(
                InvestorContact.investor_id.in_(investor_ids),
                InvestorContact.is_primary.is_(True),
            )
            .order_by(InvestorContact.created_at, InvestorContact.id)
            .all()
        )
        primary: dict[uuid.UUID, InvestorContact] = {}
        for contact in rows:
            primary.setdefault(contact.investor_id, contact)
        return primary

    def get(self, investor_id: uuid.UUID) -> tuple[Investor, Decimal, int] | None:
        return self._base_query().filter(Investor.id == investor_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, investor: Investor
    ) -> bool:
        if investor.organization_id != membership.organization_id:
            return False
        if membership.role in _ORG_VISIBLE_ROLES:
            return True
        return (
            self.db.query(InvestorContact.id)
            .filter(
                InvestorContact.investor_id == investor.id,
                InvestorContact.user_id == membership.user_id,
            )
            .first()
            is not None
        )

    def create(self, data: InvestorCreate) -> tuple[Investor, Decimal, int]:
        investor = Investor(**data.model_dump())
        self.db.add(investor)
        self.db.commit()
        self.db.refresh(investor)
        result = self.get(investor.id)  # type: ignore[invalid-argument-type]
        assert result is not None
        return result

    def update(
        self, investor_id: uuid.UUID, data: InvestorUpdate
    ) -> tuple[Investor, Decimal, int] | None:
        investor = self.db.query(Investor).filter(Investor.id == investor_id).first()
        if investor is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(investor, key, value)
        self.db.commit()
        self.db.refresh(investor)
        return self.get(investor_id)

    def has_commitments(self, investor_id: uuid.UUID) -> bool:
        return (
            self.db.query(Commitment.id)
            .filter(Commitment.investor_id == investor_id)
            .first()
            is not None
        )

    def delete(self, investor_id: uuid.UUID) -> Investor | None:
        investor = self.db.query(Investor).filter(Investor.id == investor_id).first()
        if investor is None:
            return None
        self.db.delete(investor)
        self.db.commit()
        return investor
