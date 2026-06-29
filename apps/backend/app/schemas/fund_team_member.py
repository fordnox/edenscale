from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FundTeamMemberCreate(BaseModel):
    user_id: int
    title: str | None = Field(default=None, max_length=150)
    permissions: str | None = None


class FundTeamMemberUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    permissions: str | None = None


class FundTeamMemberRead(BaseModel):
    id: int
    fund_id: int
    user_id: int
    title: str | None
    permissions: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
