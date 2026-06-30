from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field


class FundGroupCreate(BaseModel):
    organization_id: UUID4 | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class FundGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class FundGroupRead(BaseModel):
    id: UUID4
    organization_id: UUID4
    name: str
    description: str | None
    created_by_user_id: UUID4 | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
