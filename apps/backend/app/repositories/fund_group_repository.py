from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.fund_group import FundGroup
from app.schemas.fund_group import FundGroupCreate, FundGroupUpdate


class FundGroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        organization_id: int | None = None,
    ) -> list[FundGroup]:
        query = self.db.query(FundGroup)
        if organization_id is not None:
            query = query.filter(FundGroup.organization_id == organization_id)
        return query.order_by(FundGroup.id).offset(skip).limit(limit).all()

    def get(self, fund_group_id: int) -> FundGroup | None:
        return self.db.query(FundGroup).filter(FundGroup.id == fund_group_id).first()

    def create(
        self, data: FundGroupCreate, *, created_by_user_id: int | None
    ) -> FundGroup:
        fund_group = FundGroup(
            **data.model_dump(),
            created_by_user_id=created_by_user_id,
        )
        self.db.add(fund_group)
        self.db.commit()
        self.db.refresh(fund_group)
        return fund_group

    def update(self, fund_group_id: int, data: FundGroupUpdate) -> FundGroup | None:
        fund_group = self.get(fund_group_id)
        if fund_group is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(fund_group, key, value)
        self.db.commit()
        self.db.refresh(fund_group)
        return fund_group

    def has_funds(self, fund_group_id: int) -> bool:
        return (
            self.db.query(Fund).filter(Fund.fund_group_id == fund_group_id).first()
            is not None
        )

    def delete(self, fund_group_id: int) -> FundGroup | None:
        fund_group = self.get(fund_group_id)
        if fund_group is None:
            return None
        self.db.delete(fund_group)
        self.db.commit()
        return fund_group
