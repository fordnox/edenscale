from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session

from app.models.commitment import Commitment
from app.models.enums import UserRole
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.investor import InvestorCreate, InvestorUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class InvestorRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        sub = (
            self.db.query(
                Commitment.investor_id.label("investor_id"),
                func.coalesce(func.sum(Commitment.committed_amount), 0).label(
                    "total_committed"
                ),
                func.count(func.distinct(Commitment.fund_id)).label("fund_count"),
            )
            .group_by(Commitment.investor_id)
            .subquery()
        )
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
        query = self._base_query()
        if membership.role in _ORG_VISIBLE_ROLES:
            query = query.filter(Investor.organization_id == membership.organization_id)
        else:
            visible_investor_ids = select(InvestorContact.investor_id).where(
                InvestorContact.user_id == membership.user_id
            )
            query = query.filter(Investor.id.in_(visible_investor_ids))
        return query.order_by(Investor.id).offset(skip).limit(limit).all()

    def get(self, investor_id: int) -> tuple[Investor, Decimal, int] | None:
        return self._base_query().filter(Investor.id == investor_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, investor: Investor
    ) -> bool:
        if membership.role in _ORG_VISIBLE_ROLES:
            return bool(investor.organization_id == membership.organization_id)
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
        self, investor_id: int, data: InvestorUpdate
    ) -> tuple[Investor, Decimal, int] | None:
        investor = self.db.query(Investor).filter(Investor.id == investor_id).first()
        if investor is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(investor, key, value)
        self.db.commit()
        self.db.refresh(investor)
        return self.get(investor_id)

    def has_commitments(self, investor_id: int) -> bool:
        return (
            self.db.query(Commitment.id)
            .filter(Commitment.investor_id == investor_id)
            .first()
            is not None
        )

    def delete(self, investor_id: int) -> Investor | None:
        investor = self.db.query(Investor).filter(Investor.id == investor_id).first()
        if investor is None:
            return None
        self.db.delete(investor)
        self.db.commit()
        return investor
