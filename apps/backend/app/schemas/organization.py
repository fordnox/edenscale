from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrganizationType


class OrganizationCreate(BaseModel):
    type: OrganizationType
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None


class OrganizationUpdate(BaseModel):
    type: OrganizationType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class OrganizationRead(BaseModel):
    id: int
    type: OrganizationType
    name: str
    legal_name: str | None
    tax_id: str | None
    website: str | None
    description: str | None
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
