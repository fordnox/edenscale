import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.enums import UserRole
from app.models.fund import Fund
from app.models.fund_group import FundGroup
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.schemas.fund_group import FundGroupCreate, FundGroupUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class FundGroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, fund_group_id: uuid.UUID) -> FundGroup | None:
        return self.db.query(FundGroup).filter(FundGroup.id == fund_group_id).first()

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FundGroup]:
        query = self.db.query(FundGroup)
        if membership.role in _ORG_VISIBLE_ROLES:
            query = query.filter(
                FundGroup.organization_id == membership.organization_id
            )
        else:
            visible_fund_group_ids = (
                select(Fund.fund_group_id)
                .join(Commitment, Commitment.fund_id == Fund.id)
                .join(
                    InvestorContact,
                    InvestorContact.investor_id == Commitment.investor_id,
                )
                .where(
                    InvestorContact.user_id == membership.user_id,
                    Fund.fund_group_id.is_not(None),
                )
            )
            query = query.filter(FundGroup.id.in_(visible_fund_group_ids))
        return (
            query.order_by(FundGroup.created_at, FundGroup.id)
            .distinct()
            .offset(skip)
            .limit(limit)
            .all()
        )

    def membership_can_view(
        self, membership: UserOrganizationMembership, fund_group: FundGroup
    ) -> bool:
        if membership.role in _ORG_VISIBLE_ROLES:
            return bool(fund_group.organization_id == membership.organization_id)
        return (
            self.db.query(Commitment.id)
            .join(Fund, Fund.id == Commitment.fund_id)
            .join(
                InvestorContact,
                InvestorContact.investor_id == Commitment.investor_id,
            )
            .filter(
                Fund.fund_group_id == fund_group.id,
                InvestorContact.user_id == membership.user_id,
            )
            .first()
            is not None
        )

    def create(
        self, data: FundGroupCreate, *, created_by_user_id: uuid.UUID | None
    ) -> FundGroup:
        fund_group = FundGroup(
            **data.model_dump(),
            created_by_user_id=created_by_user_id,
        )
        self.db.add(fund_group)
        self.db.commit()
        self.db.refresh(fund_group)
        return fund_group

    def update(
        self, fund_group_id: uuid.UUID, data: FundGroupUpdate
    ) -> FundGroup | None:
        fund_group = self.get(fund_group_id)
        if fund_group is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(fund_group, key, value)
        self.db.commit()
        self.db.refresh(fund_group)
        return fund_group

    def has_funds(self, fund_group_id: uuid.UUID) -> bool:
        return (
            self.db.query(Fund).filter(Fund.fund_group_id == fund_group_id).first()
            is not None
        )

    def delete(self, fund_group_id: uuid.UUID) -> FundGroup | None:
        fund_group = self.get(fund_group_id)
        if fund_group is None:
            return None
        self.db.delete(fund_group)
        self.db.commit()
        return fund_group
