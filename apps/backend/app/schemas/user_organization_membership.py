from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict

from app.models.enums import UserRole
from app.schemas.organization import OrganizationRead


class MembershipBase(BaseModel):
    user_id: UUID4
    organization_id: UUID4
    role: UserRole


class MembershipCreate(MembershipBase):
    pass


class MembershipUpdate(BaseModel):
    role: UserRole


class MembershipRead(BaseModel):
    id: UUID4
    user_id: UUID4
    organization_id: UUID4
    role: UserRole
    organization: OrganizationRead
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
