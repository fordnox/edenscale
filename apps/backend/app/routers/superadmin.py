"""Superadmin control surface.

Mounted at ``/superadmin/*`` (see ``app.main``). Every route here must be
gated by :func:`app.core.rbac.require_superadmin` — these flows operate
across organizations and intentionally do *not* require the
``X-Organization-Id`` header that ``get_active_membership`` enforces for
tenant-scoped routes.

Cross-resource writes (``POST /superadmin/organizations``,
``POST /superadmin/organizations/{id}/admins``) need to land org/user/
membership rows together; `OrganizationRepository.create_with_admin` and
`UserRepository.resolve_or_create_stub` stage those rows and commit once
rather than going through the per-entity eager-commit repository helpers.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import require_superadmin
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.schemas.superadmin import (
    MembershipWithUserRead,
    SuperadminAdminAssignment,
    SuperadminDripStartResponse,
    SuperadminOrganizationCreate,
    SuperadminOrganizationCreateResponse,
    SuperadminOrganizationRead,
    SuperadminWelcomeEmailResponse,
)
from app.schemas.user import UserRead
from app.schemas.user_organization_membership import MembershipRead
from app.services.drip import fire_investor_signup
from app.services.notifications import notify_welcome

router = APIRouter(dependencies=[Depends(get_current_user)])


def _resolve_or_create_user_or_404(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
) -> User:
    user = UserRepository(db).resolve_or_create_stub(
        user_id=user_id, email=email, first_name=first_name, last_name=last_name
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get(
    "/organizations",
    response_model=list[SuperadminOrganizationRead],
    dependencies=[Depends(require_superadmin)],
)
def list_all_organizations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[SuperadminOrganizationRead]:
    rows = OrganizationRepository(db).list_with_member_counts(skip=skip, limit=limit)
    return [
        SuperadminOrganizationRead(
            id=org.id,  # type: ignore[invalid-argument-type]
            type=org.type,  # type: ignore[invalid-argument-type]
            name=org.name,  # type: ignore[invalid-argument-type]
            slug=org.slug,  # type: ignore[invalid-argument-type]
            is_active=org.is_active,  # type: ignore[invalid-argument-type]
            member_count=int(member_count or 0),
            created_at=org.created_at,  # type: ignore[invalid-argument-type]
        )
        for org, member_count in rows
    ]


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
def get_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrganizationRead:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrganizationRead.model_validate(organization)


@router.patch(
    "/organizations/{organization_id}",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
) -> OrganizationRead:
    organization = OrganizationRepository(db).update(organization_id, data)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrganizationRead.model_validate(organization)


@router.get(
    "/users",
    response_model=list[UserRead],
    dependencies=[Depends(require_superadmin)],
)
def list_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[UserRead]:
    """A page of users on the platform, across all organizations. `UserRead`
    already nests memberships → organization, so the UI can show each
    user's orgs and roles without follow-up calls."""
    users = UserRepository(db).list_all(skip=skip, limit=limit)
    return [UserRead.model_validate(user) for user in users]


@router.post(
    "/users/{user_id}/send-welcome-email",
    response_model=SuperadminWelcomeEmailResponse,
    dependencies=[Depends(require_superadmin)],
)
async def send_welcome_email(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SuperadminWelcomeEmailResponse:
    """Re-send the onboarding welcome email to a user on demand. The welcome
    template is organization-scoped, so the user must belong to at least one
    organization; the first membership's organization is used."""
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    membership = next(iter(user.memberships), None)
    if membership is None or membership.organization is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has no organization membership to welcome them into",
        )

    await notify_welcome(db, user=user, organization=membership.organization)
    return SuperadminWelcomeEmailResponse(
        user_id=user.id,  # type: ignore[invalid-argument-type]
        organization_id=membership.organization.id,
        recipient_email=user.email,  # type: ignore[invalid-argument-type]
    )


@router.post(
    "/users/{user_id}/start-investor-drip",
    response_model=SuperadminDripStartResponse,
    dependencies=[Depends(require_superadmin)],
)
async def start_investor_drip(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SuperadminDripStartResponse:
    """Fire the investor onboarding drip for a user on demand. The drip walks
    the reader through the investor portal, so the user must have at least one
    LP membership; the first LP membership's organization is used."""
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    membership = next(
        (
            m
            for m in user.memberships
            if m.role is UserRole.lp and m.organization is not None
        ),
        None,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has no LP membership to start the investor drip for",
        )

    await fire_investor_signup(user=user, organization=membership.organization)
    return SuperadminDripStartResponse(
        user_id=user.id,  # type: ignore[invalid-argument-type]
        organization_id=membership.organization.id,
        recipient_email=user.email,  # type: ignore[invalid-argument-type]
    )


@router.post(
    "/organizations",
    response_model=SuperadminOrganizationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_superadmin)],
)
def create_organization_with_admin(
    data: SuperadminOrganizationCreate,
    db: Session = Depends(get_db),
) -> SuperadminOrganizationCreateResponse:
    admin = _resolve_or_create_user_or_404(
        db,
        user_id=data.admin_user_id,
        email=data.admin_email,
        first_name=data.admin_first_name,
        last_name=data.admin_last_name,
    )

    organization, membership = OrganizationRepository(db).create_with_admin(
        OrganizationCreate(
            type=data.type,
            name=data.name,
            legal_name=data.legal_name,
            tax_id=data.tax_id,
            website=data.website,
            description=data.description,
        ),
        admin=admin,
    )

    return SuperadminOrganizationCreateResponse(
        organization=OrganizationRead.model_validate(organization),
        admin_membership=MembershipRead.model_validate(membership),
    )


@router.post(
    "/organizations/{organization_id}/admins",
    response_model=MembershipRead,
    dependencies=[Depends(require_superadmin)],
)
def assign_organization_admin(
    organization_id: uuid.UUID,
    data: SuperadminAdminAssignment,
    db: Session = Depends(get_db),
) -> MembershipRead:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    user = _resolve_or_create_user_or_404(
        db,
        user_id=data.user_id,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
    )

    membership_repo = UserOrganizationMembershipRepository(db)
    existing = membership_repo.get(user.id, organization_id)  # type: ignore[invalid-argument-type]
    if existing is not None:
        if existing.role != UserRole.admin:
            existing = membership_repo.update_role(existing.id, UserRole.admin)  # type: ignore[invalid-argument-type,assignment]
            assert existing is not None
        return MembershipRead.model_validate(existing)

    membership = membership_repo.create(
        user_id=user.id,  # type: ignore[invalid-argument-type]
        organization_id=organization_id,
        role=UserRole.admin,
    )
    return MembershipRead.model_validate(membership)


@router.patch(
    "/organizations/{organization_id}/disable",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
def disable_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrganizationRead:
    organization = OrganizationRepository(db).set_active(
        organization_id, is_active=False
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrganizationRead.model_validate(organization)


@router.patch(
    "/organizations/{organization_id}/enable",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
def enable_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrganizationRead:
    organization = OrganizationRepository(db).set_active(
        organization_id, is_active=True
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrganizationRead.model_validate(organization)


@router.get(
    "/organizations/{organization_id}/members",
    response_model=list[MembershipWithUserRead],
    dependencies=[Depends(require_superadmin)],
)
def list_organization_members(
    organization_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[MembershipWithUserRead]:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    memberships = UserOrganizationMembershipRepository(db).list_for_organization(
        organization_id, skip=skip, limit=limit
    )
    return [MembershipWithUserRead.model_validate(m) for m in memberships]
