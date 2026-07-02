from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field


class FundTeamMemberCreate(BaseModel):
    user_id: UUID4
    title: str | None = Field(default=None, max_length=150)
    permissions: str | None = None


class FundTeamMemberUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    permissions: str | None = None


class FundTeamMemberUserSummary(BaseModel):
    id: UUID4
    first_name: str
    last_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class FundTeamMemberRead(BaseModel):
    id: UUID4
    fund_id: UUID4
    user_id: UUID4
    title: str | None
    permissions: str | None
    user: FundTeamMemberUserSummary
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
