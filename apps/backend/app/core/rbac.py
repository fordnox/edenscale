"""Role-based access control helpers layered on top of the Hanko JWT check.

`get_current_user` (in `app.core.auth`) only validates the token and returns
the decoded payload. The platform also needs a local `User` row keyed by
`hanko_subject_id` so routes can authorise on `role`, scope queries by
`organization_id`, and so on. This module bridges the two:

* `get_current_user_record` — find-or-create the local `User` for the JWT
  subject, copying any name/email claims the IdP supplied.
* `require_superadmin` — direct dependency that 403s unless the resolved
  user is a superadmin. Superadmins are defined purely by the
  `SUPERADMIN_EMAIL` setting (never stored in the database); used for
  `/superadmin/*` routes that operate across organizations and so do not
  require an `X-Organization-Id` header.
* `get_active_membership` — resolves the `UserOrganizationMembership` the
  caller is acting through, based on the `X-Organization-Id` header. Used
  for org-scoped routes where the user may belong to multiple orgs.
  (Investor-portal routes under `/investor` don't use this — they resolve
  access from contact links via `app.core.investor_access`.)
* `require_membership_roles` — dependency factory that 403s when the active
  membership's role is not in the allow-list.
"""

import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.middleware.audit_context import set_audit_user
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)


def get_current_user_record(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the local `User` row for the authenticated JWT subject.

    `get_current_user` (in `app.core.auth`) already verifies the token and
    resolves — or auto-provisions on first sign-in — the local `User` row via
    `UserRepository.get_or_provision_by_hanko_id` (including binding
    pre-provisioned seed users by verified email). This dependency simply
    records the resolved user for audit logging and returns it, so routes have
    a single place to layer role checks on top.
    """
    set_audit_user(current_user.id)  # type: ignore[invalid-argument-type]
    return current_user


def require_superadmin(
    current_user: User = Depends(get_current_user_record),
) -> User:
    """Allow the request only when the resolved user is a superadmin.

    Superadmin is a config-defined identity (`SUPERADMIN_EMAIL`), not a
    database role. Unlike `require_membership_roles`, this does NOT depend on
    `get_active_membership` and so does not require an `X-Organization-Id`
    header — the `/superadmin/*` control surface acts across all
    organizations.
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin role required",
        )
    return current_user


def require_tenant_user(
    current_user: User = Depends(get_current_user_record),
) -> User:
    """Reject platform administrators from tenant-only, non-membership flows."""
    if current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmins must use /superadmin endpoints",
        )
    return current_user


def get_active_membership(
    x_organization_id: uuid.UUID | None = Header(
        default=None, alias="X-Organization-Id"
    ),
    current_user: User = Depends(get_current_user_record),
    db: Session = Depends(get_db),
) -> UserOrganizationMembership:
    """Resolve the membership the caller is currently acting through.

    Superadmins are intentionally rejected here: their complete API surface is
    mounted under ``/superadmin`` and never impersonates a tenant membership.

    Resolution rules:

    1. If the `X-Organization-Id` header is present:
       - Return the matching `(user_id, organization_id)` membership row.
       - Otherwise raise 403 "Not a member of this organization".
    2. If the header is missing:
       - If the user has exactly one membership, use it.
       - If the user has zero or multiple memberships, raise 400 with
         "X-Organization-Id required".
    """
    repo = UserOrganizationMembershipRepository(db)

    if current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmins must use /superadmin endpoints",
        )

    if x_organization_id is not None:
        membership = repo.get(current_user.id, x_organization_id)  # type: ignore[invalid-argument-type]
        if membership is not None:
            return membership
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    memberships = repo.list_for_user(current_user.id)  # type: ignore[invalid-argument-type]
    if len(memberships) == 1:
        return memberships[0]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="X-Organization-Id required",
    )


def require_membership_roles(
    *allowed: UserRole,
) -> Callable[[UserOrganizationMembership], UserOrganizationMembership]:
    """Return a dependency that allows the request only when the active
    membership's role is in `allowed`.

    A user who is `lp` globally but `admin` of Org B will be treated as
    `admin` when acting through their Org B membership.
    """

    def _dep(
        membership: UserOrganizationMembership = Depends(get_active_membership),
    ) -> UserOrganizationMembership:
        if membership.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return membership

    return _dep
