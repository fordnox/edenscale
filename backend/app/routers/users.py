from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import (
    get_current_user_record,
    require_membership_roles,
    require_roles,
)
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserCreate,
    UserRead,
    UserRoleUpdate,
    UserSelfUpdate,
    UserUpdate,
)

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: User = Depends(get_current_user_record),
):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    data: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = UserRepository(db)
    updated = repo.update(
        current_user.id,  # type: ignore[invalid-argument-type]
        UserUpdate(**data.model_dump(exclude_unset=True)),
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return updated


@router.get("", response_model=list[UserRead])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = UserRepository(db)
    return repo.list_by_organization(
        organization_id=membership.organization_id,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def invite_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    if membership.role is UserRole.superadmin and membership.id is None:
        # Synthesized superadmin membership — no real per-org row. Phase 04
        # replaces this endpoint with POST /organizations/{id}/memberships.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /organizations/{id}/memberships to add users (Phase 04)",
        )
    payload = data.model_dump()
    payload["organization_id"] = membership.organization_id
    repo = UserRepository(db)
    if repo.get_by_email(payload["email"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    return repo.create(UserCreate(**payload))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = UserRepository(db)
    target = repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if (
        membership.role is not UserRole.superadmin
        and target.organization_id != membership.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit users outside your organization",
        )
    return repo.update(user_id, data)


@router.patch(
    "/{user_id}/role",
    response_model=UserRead,
    dependencies=[Depends(require_roles(UserRole.admin, UserRole.superadmin))],
)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.update_role(user_id, data.role)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user
