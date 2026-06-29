from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FundGroupCreate(BaseModel):
    organization_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class FundGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class FundGroupRead(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None
    created_by_user_id: int | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
