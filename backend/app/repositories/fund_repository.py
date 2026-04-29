from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session

from app.models.commitment import Commitment
from app.models.enums import FundStatus, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user import User
from app.schemas.fund import FundCreate, FundUpdate


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

    def list_for_user(
        self,
        user: User,
        skip: int = 0,
        limit: int = 100,
    ) -> list[tuple[Fund, Decimal]]:
        query = self._base_query()
        if user.role is UserRole.admin:
            pass
        elif user.role is UserRole.fund_manager:
            if user.organization_id is None:
                return []
            query = query.filter(Fund.organization_id == user.organization_id)
        else:
            visible_fund_ids = (
                select(Commitment.fund_id)
                .join(
                    InvestorContact,
                    InvestorContact.investor_id == Commitment.investor_id,
                )
                .where(InvestorContact.user_id == user.id)
            )
            query = query.filter(Fund.id.in_(visible_fund_ids))
        return query.order_by(Fund.id).offset(skip).limit(limit).all()

    def get(self, fund_id: int) -> tuple[Fund, Decimal] | None:
        return self._base_query().filter(Fund.id == fund_id).first()

    def user_can_view(self, user: User, fund: Fund) -> bool:
        if user.role is UserRole.admin:
            return True
        if user.role is UserRole.fund_manager:
            return bool(fund.organization_id == user.organization_id)
        return (
            self.db.query(Commitment.id)
            .join(
                InvestorContact,
                InvestorContact.investor_id == Commitment.investor_id,
            )
            .filter(
                Commitment.fund_id == fund.id,
                InvestorContact.user_id == user.id,
            )
            .first()
            is not None
        )

    def create(self, data: FundCreate) -> tuple[Fund, Decimal]:
        fund = Fund(**data.model_dump())
        self.db.add(fund)
        self.db.commit()
        self.db.refresh(fund)
        result = self.get(fund.id)  # type: ignore[invalid-argument-type]
        assert result is not None
        return result

    def update(self, fund_id: int, data: FundUpdate) -> tuple[Fund, Decimal] | None:
        fund = self.db.query(Fund).filter(Fund.id == fund_id).first()
        if fund is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(fund, key, value)
        self.db.commit()
        self.db.refresh(fund)
        return self.get(fund_id)

    def archive(self, fund_id: int) -> tuple[Fund, Decimal] | None:
        fund = self.db.query(Fund).filter(Fund.id == fund_id).first()
        if fund is None:
            return None
        fund.status = FundStatus.archived
        self.db.commit()
        self.db.refresh(fund)
        return self.get(fund_id)
