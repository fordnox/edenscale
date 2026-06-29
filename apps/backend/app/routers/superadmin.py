"""Superadmin control surface.

Mounted at ``/superadmin/*`` (see ``app.main``). Every route here must be
gated by :func:`app.core.rbac.require_superadmin` — these flows operate
across organizations and intentionally do *not* require the
``X-Organization-Id`` header that ``get_active_membership`` enforces for
tenant-scoped routes.

Cross-resource writes (``POST /superadmin/organizations``,
``POST /superadmin/organizations/{id}/admins``) need to land org/user/
membership rows together, so they bypass the eager-commit repository
helpers and stage everything on the request session before a single
final commit.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_superadmin
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.organization import OrganizationRead
from app.schemas.superadmin import (
    MembershipWithUserRead,
    SuperadminAdminAssignment,
    SuperadminOrganizationCreate,
    SuperadminOrganizationCreateResponse,
    SuperadminOrganizationRead,
)
from app.schemas.user_organization_membership import MembershipRead

router = APIRouter()


def _resolve_or_create_user(
    db: Session,
    *,
    user_id: int | None,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
) -> User:
    """Return the `User` referenced by ``user_id`` or ``email``.

    If ``email`` is given and no user exists for it yet, a stub row is
    staged on the session (not committed) with ``hanko_subject_id=None``
    so that ``get_current_user_record`` claims it on first sign-in.
    """
    if user_id is not None:
        user = UserRepository(db).get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    assert email is not None
    existing = UserRepository(db).get_by_email(email)
    if existing is not None:
        return existing

    stub = User(
        role=UserRole.lp,
        first_name=first_name or "",
        last_name=last_name or "",
        email=email,
        hanko_subject_id=None,
    )
    db.add(stub)
    db.flush()
    return stub


@router.get(
    "/organizations",
    response_model=list[SuperadminOrganizationRead],
    dependencies=[Depends(require_superadmin)],
)
async def list_all_organizations(
    db: Session = Depends(get_db),
) -> list[SuperadminOrganizationRead]:
    rows = (
        db.query(
            Organization,
            func.count(UserOrganizationMembership.id).label("member_count"),
        )
        .outerjoin(
            UserOrganizationMembership,
            UserOrganizationMembership.organization_id == Organization.id,
        )
        .group_by(Organization.id)
        .order_by(Organization.id)
        .all()
    )
    return [
        SuperadminOrganizationRead(
            id=org.id,
            type=org.type,
            name=org.name,
            is_active=org.is_active,
            member_count=int(member_count or 0),
            created_at=org.created_at,
        )
        for org, member_count in rows
    ]


@router.post(
    "/organizations",
    response_model=SuperadminOrganizationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_superadmin)],
)
async def create_organization_with_admin(
    data: SuperadminOrganizationCreate,
    db: Session = Depends(get_db),
) -> SuperadminOrganizationCreateResponse:
    admin = _resolve_or_create_user(
        db,
        user_id=data.admin_user_id,
        email=data.admin_email,
        first_name=data.admin_first_name,
        last_name=data.admin_last_name,
    )

    organization = Organization(
        type=data.type,
        name=data.name,
        legal_name=data.legal_name,
        tax_id=data.tax_id,
        website=data.website,
        description=data.description,
    )
    db.add(organization)
    db.flush()

    membership = UserOrganizationMembership(
        user_id=admin.id,
        organization_id=organization.id,
        role=UserRole.admin,
    )
    db.add(membership)
    db.commit()
    db.refresh(organization)
    db.refresh(membership)

    return SuperadminOrganizationCreateResponse(
        organization=OrganizationRead.model_validate(organization),
        admin_membership=MembershipRead.model_validate(membership),
    )


@router.post(
    "/organizations/{organization_id}/admins",
    response_model=MembershipRead,
    dependencies=[Depends(require_superadmin)],
)
async def assign_organization_admin(
    organization_id: int,
    data: SuperadminAdminAssignment,
    db: Session = Depends(get_db),
) -> MembershipRead:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    user = _resolve_or_create_user(
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
            existing.role = UserRole.admin
            db.commit()
            db.refresh(existing)
        return MembershipRead.model_validate(existing)

    membership = membership_repo.create(
        user_id=user.id,  # type: ignore[invalid-argument-type]
        organization_id=organization_id,
        role=UserRole.admin,
    )
    return MembershipRead.model_validate(membership)


def _set_organization_active(
    db: Session, organization_id: int, *, is_active: bool
) -> Organization:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    organization.is_active = is_active
    db.commit()
    db.refresh(organization)
    return organization


@router.patch(
    "/organizations/{organization_id}/disable",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
async def disable_organization(
    organization_id: int,
    db: Session = Depends(get_db),
) -> OrganizationRead:
    organization = _set_organization_active(db, organization_id, is_active=False)
    return OrganizationRead.model_validate(organization)


@router.patch(
    "/organizations/{organization_id}/enable",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
async def enable_organization(
    organization_id: int,
    db: Session = Depends(get_db),
) -> OrganizationRead:
    organization = _set_organization_active(db, organization_id, is_active=True)
    return OrganizationRead.model_validate(organization)


@router.get(
    "/organizations/{organization_id}/members",
    response_model=list[MembershipWithUserRead],
    dependencies=[Depends(require_superadmin)],
)
async def list_organization_members(
    organization_id: int,
    db: Session = Depends(get_db),
) -> list[MembershipWithUserRead]:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    memberships = UserOrganizationMembershipRepository(db).list_for_organization(
        organization_id
    )
    return [MembershipWithUserRead.model_validate(m) for m in memberships]
