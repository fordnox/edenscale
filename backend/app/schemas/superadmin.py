"""Schemas for the `/superadmin/*` control surface.

These payloads exist because the superadmin views are denormalized in ways
the per-tenant `OrganizationRead` / `MembershipRead` are not:

* `SuperadminOrganizationRead` adds a precomputed `member_count` so the
  superadmin org list does not need an N+1 to render the roster size.
* `SuperadminOrganizationCreate` lets a superadmin spin up an org and its
  founding admin in one call by supplying either an existing `admin_user_id`
  or an `admin_email` (a stub user is created if no row matches yet).
* `SuperadminAdminAssignment` is the body for the standalone
  `POST /superadmin/organizations/{id}/admins` flow — same `user_id` /
  `email` rules, but for already-existing orgs.
* `MembershipWithUserRead` is the roster payload — nested `UserRead` is
  needed so the UI can render names/emails without a follow-up call.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.enums import OrganizationType, UserRole
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.schemas.user import UserRead
from app.schemas.user_organization_membership import MembershipRead


class SuperadminOrganizationRead(BaseModel):
    id: int
    type: OrganizationType
    name: str
    is_active: bool
    member_count: int
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SuperadminOrganizationCreate(OrganizationCreate):
    admin_user_id: int | None = None
    admin_email: EmailStr | None = None
    admin_first_name: str | None = Field(default=None, min_length=1, max_length=100)
    admin_last_name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _require_one_admin_target(self) -> "SuperadminOrganizationCreate":
        if (self.admin_user_id is None) == (self.admin_email is None):
            raise ValueError("Provide exactly one of admin_user_id or admin_email")
        return self


class SuperadminOrganizationCreateResponse(BaseModel):
    organization: OrganizationRead
    admin_membership: MembershipRead


class SuperadminAdminAssignment(BaseModel):
    user_id: int | None = None
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def _require_one_target(self) -> "SuperadminAdminAssignment":
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Provide exactly one of user_id or email")
        return self


class MembershipWithUserRead(BaseModel):
    id: int
    user_id: int
    organization_id: int
    role: UserRole
    user: UserRead
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
