from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.fund_group_repository import FundGroupRepository
from app.schemas.fund_group import (
    FundGroupCreate,
    FundGroupRead,
    FundGroupUpdate,
)

router = APIRouter()


@router.get("", response_model=list[FundGroupRead])
async def list_fund_groups(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = FundGroupRepository(db)
    if current_user.role is UserRole.fund_manager:
        if current_user.organization_id is None:
            return []
        return repo.list(
            skip=skip, limit=limit, organization_id=current_user.organization_id  # type: ignore[invalid-argument-type]
        )
    return repo.list(skip=skip, limit=limit)


@router.get("/{fund_group_id}", response_model=FundGroupRead)
async def get_fund_group(
    fund_group_id: int,
    db: Session = Depends(get_db),
    # TODO: scope to LP commitments — for now restrict reads to fund_manager+admin.
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = FundGroupRepository(db)
    fund_group = repo.get(fund_group_id)
    if fund_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund group not found"
        )
    if (
        current_user.role is UserRole.fund_manager
        and fund_group.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view fund groups outside your organization",
        )
    return fund_group


@router.post("", response_model=FundGroupRead, status_code=status.HTTP_201_CREATED)
async def create_fund_group(
    data: FundGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    payload = data.model_dump()
    if current_user.role is UserRole.fund_manager:
        if current_user.organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fund managers must belong to an organization to create fund groups",
            )
        payload["organization_id"] = current_user.organization_id
    elif payload.get("organization_id") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization_id is required",
        )
    repo = FundGroupRepository(db)
    return repo.create(
        FundGroupCreate(**payload),
        created_by_user_id=current_user.id,  # type: ignore[invalid-argument-type]
    )


@router.patch("/{fund_group_id}", response_model=FundGroupRead)
async def update_fund_group(
    fund_group_id: int,
    data: FundGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = FundGroupRepository(db)
    fund_group = repo.get(fund_group_id)
    if fund_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund group not found"
        )
    if (
        current_user.role is UserRole.fund_manager
        and fund_group.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit fund groups outside your organization",
        )
    return repo.update(fund_group_id, data)


@router.delete("/{fund_group_id}", response_model=FundGroupRead)
async def delete_fund_group(
    fund_group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = FundGroupRepository(db)
    fund_group = repo.get(fund_group_id)
    if fund_group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund group not found"
        )
    if (
        current_user.role is UserRole.fund_manager
        and fund_group.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete fund groups outside your organization",
        )
    if repo.has_funds(fund_group_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete fund group with associated funds",
        )
    return repo.delete(fund_group_id)
