from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_roles
from app.models.enums import UserRole
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
    dependencies=[Depends(require_roles(UserRole.admin, UserRole.fund_manager))],
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
    dependencies=[Depends(require_roles(UserRole.admin, UserRole.fund_manager))],
)
async def update_organization(
    organization_id: int,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
):
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
    dependencies=[Depends(require_roles(UserRole.admin))],
)
async def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db),
):
    repo = OrganizationRepository(db)
    organization = repo.soft_delete(organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return organization
