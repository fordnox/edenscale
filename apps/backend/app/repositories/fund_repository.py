import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session

from app.core.slugs import generate_unique_slug
from app.models.commitment import Commitment
from app.models.enums import FundStatus, UserRole
from app.models.fund import Fund
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.lp_scope import lp_visible_investor_ids
from app.schemas.fund import FundCreate, FundUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class FundRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        sub = (
            self.db.query(
                Commitment.fund_id.label("fund_id"),
                func.coalesce(func.sum(Commitment.committed_amount), 0).label(
                    "current_size"
                ),
            )
            .group_by(Commitment.fund_id)
            .subquery()
        )
        return self.db.query(
            Fund, func.coalesce(sub.c.current_size, 0).label("current_size")
        ).outerjoin(sub, sub.c.fund_id == Fund.id)

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        skip: int = 0,
        limit: int = 100,
    ) -> list[tuple[Fund, Decimal]]:
        query = self._base_query().filter(
            Fund.organization_id == membership.organization_id
        )
        if membership.role not in _ORG_VISIBLE_ROLES:
            visible_fund_ids = select(Commitment.fund_id).where(
                Commitment.investor_id.in_(lp_visible_investor_ids(membership))
            )
            query = query.filter(Fund.id.in_(visible_fund_ids))
        return query.order_by(Fund.created_at, Fund.id).offset(skip).limit(limit).all()

    def get(self, fund_id: uuid.UUID) -> tuple[Fund, Decimal] | None:
        return self._base_query().filter(Fund.id == fund_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, fund: Fund
    ) -> bool:
        if fund.organization_id != membership.organization_id:
            return False
        if membership.role in _ORG_VISIBLE_ROLES:
            return True
        return (
            self.db.query(Commitment.id)
            .filter(
                Commitment.fund_id == fund.id,
                Commitment.investor_id.in_(lp_visible_investor_ids(membership)),
            )
            .first()
            is not None
        )

    def create(self, data: FundCreate) -> tuple[Fund, Decimal]:
        assert data.organization_id is not None
        organization_id = data.organization_id
        slug = generate_unique_slug(
            data.name,
            exists=lambda candidate: self.db.query(Fund.id)
            .filter(
                Fund.organization_id == organization_id,
                Fund.slug == candidate,
            )
            .first()
            is not None,
        )
        fund = Fund(**data.model_dump(), slug=slug)
        self.db.add(fund)
        self.db.commit()
        self.db.refresh(fund)
        result = self.get(fund.id)  # type: ignore[invalid-argument-type]
        assert result is not None
        return result

    def update(
        self, fund_id: uuid.UUID, data: FundUpdate
    ) -> tuple[Fund, Decimal] | None:
        fund = self.db.query(Fund).filter(Fund.id == fund_id).first()
        if fund is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(fund, key, value)
        self.db.commit()
        self.db.refresh(fund)
        return self.get(fund_id)

    def archive(self, fund_id: uuid.UUID) -> tuple[Fund, Decimal] | None:
        fund = self.db.query(Fund).filter(Fund.id == fund_id).first()
        if fund is None:
            return None
        fund.status = FundStatus.archived
        self.db.commit()
        self.db.refresh(fund)
        return self.get(fund_id)

    def overview_totals(self, fund_id: uuid.UUID) -> tuple[Decimal, Decimal, Decimal]:
        """Return `(committed, called, distributed)` summed across the fund's commitments."""
        row = (
            self.db.query(
                func.coalesce(func.sum(Commitment.committed_amount), 0),
                func.coalesce(func.sum(Commitment.called_amount), 0),
                func.coalesce(func.sum(Commitment.distributed_amount), 0),
            )
            .filter(Commitment.fund_id == fund_id)
            .one()
        )
        return Decimal(row[0] or 0), Decimal(row[1] or 0), Decimal(row[2] or 0)
