import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import (
    get_current_user_record,
    require_membership_roles,
)
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    OrgMemberRead,
    UserRead,
    UserRoleUpdate,
    UserSelfUpdate,
    UserUpdate,
)
from app.schemas.user_organization_membership import MembershipRead

router = APIRouter(dependencies=[Depends(get_current_user)])


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


@router.get("/me/memberships", response_model=list[MembershipRead])
async def list_my_memberships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = UserOrganizationMembershipRepository(db)
    return repo.list_for_user(current_user.id)  # type: ignore[invalid-argument-type]


@router.get("", response_model=list[OrgMemberRead])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    """List the active organization's members.

    Membership rows are the source of truth (invitation acceptance only
    creates a membership), so ``role`` is the member's role in this org —
    users have no global role.
    """
    repo = UserOrganizationMembershipRepository(db)
    rows = repo.list_org_members(
        membership.organization_id,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )
    return [
        OrgMemberRead(
            **UserRead.model_validate(user).model_dump(),
            role=m.role,  # type: ignore[invalid-argument-type]
        )
        for m, user in rows
    ]


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    repo = UserRepository(db)
    target = repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if (
        UserOrganizationMembershipRepository(db).get(
            user_id,
            membership.organization_id,  # type: ignore[invalid-argument-type]
        )
        is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit users outside your organization",
        )
    return repo.update(user_id, data)


@router.patch("/{user_id}/role", response_model=OrgMemberRead)
async def update_user_role(
    user_id: uuid.UUID,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin)
    ),
):
    """Change a member's role within the caller's active organization.

    Roles live exclusively on membership rows — this updates the target's
    membership in the caller's org. The response's ``role`` mirrors the new
    membership role, matching what ``GET /users`` returns.
    """
    target = UserRepository(db).get_by_id(user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    membership_repo = UserOrganizationMembershipRepository(db)
    target_membership = membership_repo.get(
        user_id,
        membership.organization_id,  # type: ignore[invalid-argument-type]
    )
    if target_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this organization",
        )
    updated = membership_repo.update_role(
        target_membership.id,  # type: ignore[invalid-argument-type]
        data.role,
    )
    assert updated is not None
    return OrgMemberRead(
        **UserRead.model_validate(target).model_dump(),
        role=updated.role,  # type: ignore[invalid-argument-type]
    )
