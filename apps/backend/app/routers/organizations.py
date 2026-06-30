import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import (
    get_current_user_record,
    require_membership_roles,
    require_superadmin,
)
from app.models.enums import OrganizationType, UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationOnboardingCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.schemas.user_organization_membership import MembershipRead

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/self-serve",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_self_serve(
    data: OrganizationOnboardingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    """Onboarding entry point for a signed-in user with no organization.

    Creates a new `fund_manager_firm` organization and makes the caller its
    `admin`, so they can immediately create and manage their own fund without
    waiting on an invitation.
    """
    repo = OrganizationRepository(db)
    organization = repo.create(
        OrganizationCreate(
            type=OrganizationType.fund_manager_firm,
            name=data.name,
            legal_name=data.legal_name,
            website=data.website,
            description=data.description,
        )
    )
    membership = UserOrganizationMembershipRepository(db).create(
        user_id=current_user.id,  # type: ignore[invalid-argument-type]
        organization_id=organization.id,  # type: ignore[invalid-argument-type]
        role=UserRole.admin,
    )
    return membership


@router.get("", response_model=list[OrganizationRead])
async def list_organizations(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    repo = OrganizationRepository(db)
    return repo.list(skip=skip, limit=limit, include_inactive=include_inactive)


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = OrganizationRepository(db)
    organization = repo.get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_superadmin)],
)
async def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db),
):
    repo = OrganizationRepository(db)
    return repo.create(data)


@router.patch(
    "/{organization_id}",
    response_model=OrganizationRead,
)
async def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin)
    ),
):
    if membership.organization_id != organization_id:
        # The active membership (resolved from X-Organization-Id) does not
        # match the path. Refuse rather than silently editing a different org.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit an organization you are not an admin of",
        )
    repo = OrganizationRepository(db)
    organization = repo.update(organization_id, data)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization


@router.delete(
    "/{organization_id}",
    response_model=OrganizationRead,
    dependencies=[Depends(require_superadmin)],
)
async def delete_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = OrganizationRepository(db)
    organization = repo.get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    # Cascade: delete every membership for this org so re-enabling does not
    # silently restore old access. Memberships have no `is_active` column,
    # so hard-delete is the only "deactivate" available — distinct from
    # PATCH /superadmin/organizations/{id}/disable, which preserves them.
    UserOrganizationMembershipRepository(db).delete_all_for_organization(
        organization_id
    )
    deactivated = repo.soft_delete(organization_id)
    assert deactivated is not None
    return deactivated
