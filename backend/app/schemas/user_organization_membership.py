from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole
from app.schemas.organization import OrganizationRead


class MembershipBase(BaseModel):
    user_id: int
    organization_id: int
    role: UserRole


class MembershipCreate(MembershipBase):
    pass


class MembershipUpdate(BaseModel):
    role: UserRole


class MembershipRead(BaseModel):
    id: int
    user_id: int
    organization_id: int
    role: UserRole
    organization: OrganizationRead
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
