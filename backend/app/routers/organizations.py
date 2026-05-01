from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_membership_roles, require_superadmin
from app.models.enums import UserRole
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)

router = APIRouter()


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
    organization_id: int,
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
    organization_id: int,
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
    organization_id: int,
    db: Session = Depends(get_db),
):
    repo = OrganizationRepository(db)
    organization = repo.get(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    organization.is_active = False
    # Cascade: delete every membership for this org so re-enabling does not
    # silently restore old access. Memberships have no `is_active` column,
    # so hard-delete is the only "deactivate" available — distinct from
    # PATCH /superadmin/organizations/{id}/disable, which preserves them.
    db.query(UserOrganizationMembership).filter(
        UserOrganizationMembership.organization_id == organization_id
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(organization)
    return organization
