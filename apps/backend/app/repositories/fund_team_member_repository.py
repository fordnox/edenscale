import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.fund_team_member import FundTeamMember
from app.schemas.fund_team_member import (
    FundTeamMemberCreate,
    FundTeamMemberUpdate,
)


class FundTeamMemberRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_fund(
        self,
        fund_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FundTeamMember]:
        return (
            self.db.query(FundTeamMember)
            .options(joinedload(FundTeamMember.user))
            .filter(FundTeamMember.fund_id == fund_id)
            .order_by(FundTeamMember.created_at, FundTeamMember.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get(self, member_id: uuid.UUID) -> FundTeamMember | None:
        return (
            self.db.query(FundTeamMember)
            .options(joinedload(FundTeamMember.user))
            .filter(FundTeamMember.id == member_id)
            .first()
        )

    def get_by_fund_and_user(
        self, fund_id: uuid.UUID, user_id: uuid.UUID
    ) -> FundTeamMember | None:
        return (
            self.db.query(FundTeamMember)
            .filter(
                FundTeamMember.fund_id == fund_id,
                FundTeamMember.user_id == user_id,
            )
            .first()
        )

    def create(self, fund_id: uuid.UUID, data: FundTeamMemberCreate) -> FundTeamMember:
        member = FundTeamMember(fund_id=fund_id, **data.model_dump())
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def update(
        self, member_id: uuid.UUID, data: FundTeamMemberUpdate
    ) -> FundTeamMember | None:
        member = self.get(member_id)
        if member is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(member, key, value)
        self.db.commit()
        self.db.refresh(member)
        return member

    def delete(self, member_id: uuid.UUID) -> FundTeamMember | None:
        member = self.get(member_id)
        if member is None:
            return None
        self.db.delete(member)
        self.db.commit()
        return member
