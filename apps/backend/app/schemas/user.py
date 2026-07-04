from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.user_organization_membership import MembershipRead


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=150)
    hanko_subject_id: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=150)
    is_active: bool | None = None


class UserSelfUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=150)


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserRead(BaseModel):
    id: UUID4
    first_name: str
    last_name: str
    email: str
    phone: str | None
    title: str | None
    is_active: bool
    # Computed from SUPERADMIN_EMAIL config (User.is_superadmin property) —
    # superadmins are never stored in the database.
    is_superadmin: bool = False
    last_login_at: datetime | None
    hanko_subject_id: str | None
    created_at: datetime | None
    updated_at: datetime | None
    memberships: list[MembershipRead] = []

    model_config = ConfigDict(from_attributes=True)


class OrgMemberRead(UserRead):
    """A user seen through their membership in the active organization —
    ``role`` is the per-org membership role (users have no global role)."""

    role: UserRole
