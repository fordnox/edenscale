from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session

from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.distribution_item import DistributionItem
from app.models.enums import CommitmentStatus, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.commitment import CommitmentCreate, CommitmentUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class CommitmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Commitment)

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        *,
        fund_id: int | None = None,
        investor_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Commitment]:
        query = self._base_query()
        if membership.role in _ORG_VISIBLE_ROLES:
            query = query.join(Fund, Fund.id == Commitment.fund_id).filter(
                Fund.organization_id == membership.organization_id
            )
        else:
            visible_investor_ids = select(InvestorContact.investor_id).where(
                InvestorContact.user_id == membership.user_id
            )
            query = query.filter(Commitment.investor_id.in_(visible_investor_ids))
        if fund_id is not None:
            query = query.filter(Commitment.fund_id == fund_id)
        if investor_id is not None:
            query = query.filter(Commitment.investor_id == investor_id)
        return query.order_by(Commitment.id).offset(skip).limit(limit).all()

    def get(self, commitment_id: int) -> Commitment | None:
        return self._base_query().filter(Commitment.id == commitment_id).first()

    def get_by_fund_and_investor(
        self, fund_id: int, investor_id: int
    ) -> Commitment | None:
        return (
            self._base_query()
            .filter(
                Commitment.fund_id == fund_id,
                Commitment.investor_id == investor_id,
            )
            .first()
        )

    def membership_can_view(
        self, membership: UserOrganizationMembership, commitment: Commitment
    ) -> bool:
        if membership.role in _ORG_VISIBLE_ROLES:
            fund = self.db.query(Fund).filter(Fund.id == commitment.fund_id).first()
            if fund is None:
                return False
            return bool(fund.organization_id == membership.organization_id)
        return (
            self.db.query(InvestorContact.id)
            .filter(
                InvestorContact.investor_id == commitment.investor_id,
                InvestorContact.user_id == membership.user_id,
            )
            .first()
            is not None
        )

    def create(self, data: CommitmentCreate) -> Commitment:
        commitment = Commitment(**data.model_dump())
        self.db.add(commitment)
        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def update(self, commitment_id: int, data: CommitmentUpdate) -> Commitment | None:
        commitment = self.get(commitment_id)
        if commitment is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(commitment, key, value)
        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def set_status(
        self, commitment_id: int, new_status: CommitmentStatus
    ) -> Commitment | None:
        commitment = self.get(commitment_id)
        if commitment is None:
            return None
        commitment.status = new_status
        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def recompute_totals(self, commitment_id: int) -> Commitment | None:
        commitment = self.get(commitment_id)
        if commitment is None:
            return None
        called = (
            self.db.query(func.coalesce(func.sum(CapitalCallItem.amount_paid), 0))
            .filter(CapitalCallItem.commitment_id == commitment_id)
            .scalar()
        )
        distributed = (
            self.db.query(func.coalesce(func.sum(DistributionItem.amount_paid), 0))
            .filter(DistributionItem.commitment_id == commitment_id)
            .scalar()
        )
        commitment.called_amount = Decimal(called or 0)
        commitment.distributed_amount = Decimal(distributed or 0)
        self.db.flush()
        return commitment
