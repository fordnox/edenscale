from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import InvitationStatus, UserRole
from app.schemas.organization import OrganizationRead


def _reject_superadmin(role: UserRole) -> UserRole:
    if role is UserRole.superadmin:
        raise ValueError("superadmin role cannot be granted via invitation")
    return role


class InvitationCreate(BaseModel):
    organization_id: int
    email: EmailStr
    role: UserRole

    @field_validator("role")
    @classmethod
    def _no_superadmin(cls, value: UserRole) -> UserRole:
        return _reject_superadmin(value)


class InvitationAccept(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class InvitationRead(BaseModel):
    id: int
    organization_id: int
    email: str
    role: UserRole
    token: str
    status: InvitationStatus
    expires_at: datetime
    invited_by_user_id: int | None
    accepted_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    organization: OrganizationRead

    model_config = ConfigDict(from_attributes=True)


class InvitationListItem(BaseModel):
    id: int
    organization_id: int
    email: str
    role: UserRole
    status: InvitationStatus
    expires_at: datetime
    invited_by_user_id: int | None
    accepted_at: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
