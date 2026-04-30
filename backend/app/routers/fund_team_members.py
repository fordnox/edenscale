from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.enums import UserRole
from app.models.fund import Fund
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.fund_repository import FundRepository
from app.repositories.fund_team_member_repository import FundTeamMemberRepository
from app.schemas.fund_team_member import (
    FundTeamMemberCreate,
    FundTeamMemberRead,
    FundTeamMemberUpdate,
)

router = APIRouter()


def _load_fund_or_404(db: Session, fund_id: int) -> Fund:
    repo = FundRepository(db)
    row = repo.get(fund_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    return row[0]


def _ensure_org_scope(membership: UserOrganizationMembership, fund: Fund) -> None:
    if fund.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage team members for funds outside your organization",
        )


@router.get("/{fund_id}/team", response_model=list[FundTeamMemberRead])
async def list_team_members(
    fund_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    fund = _load_fund_or_404(db, fund_id)
    if not FundRepository(db).membership_can_view(membership, fund):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view team members for this fund",
        )
    return FundTeamMemberRepository(db).list_for_fund(fund_id, skip=skip, limit=limit)


@router.post(
    "/{fund_id}/team",
    response_model=FundTeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    fund_id: int,
    data: FundTeamMemberCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    fund = _load_fund_or_404(db, fund_id)
    _ensure_org_scope(membership, fund)
    repo = FundTeamMemberRepository(db)
    if repo.get_by_fund_and_user(fund_id, data.user_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a team member of this fund",
        )
    try:
        return repo.create(fund_id, data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a team member of this fund",
        ) from exc


@router.patch(
    "/{fund_id}/team/{member_id}",
    response_model=FundTeamMemberRead,
)
async def update_team_member(
    fund_id: int,
    member_id: int,
    data: FundTeamMemberUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    fund = _load_fund_or_404(db, fund_id)
    _ensure_org_scope(membership, fund)
    repo = FundTeamMemberRepository(db)
    member = repo.get(member_id)
    if member is None or member.fund_id != fund_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found"
        )
    updated = repo.update(member_id, data)
    assert updated is not None
    return updated


@router.delete(
    "/{fund_id}/team/{member_id}",
    response_model=FundTeamMemberRead,
)
async def remove_team_member(
    fund_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    fund = _load_fund_or_404(db, fund_id)
    _ensure_org_scope(membership, fund)
    repo = FundTeamMemberRepository(db)
    member = repo.get(member_id)
    if member is None or member.fund_id != fund_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found"
        )
    deleted = repo.delete(member_id)
    assert deleted is not None
    return deleted
