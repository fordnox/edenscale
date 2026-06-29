from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.enums import UserRole
from app.models.fund import Fund as FundModel
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.fund_repository import FundRepository
from app.schemas.fund import (
    FundCreate,
    FundListItem,
    FundOverview,
    FundRead,
    FundUpdate,
)

router = APIRouter()


def _to_read_dict(fund: FundModel, current_size: Decimal) -> dict:
    return {
        "id": fund.id,
        "organization_id": fund.organization_id,
        "fund_group_id": fund.fund_group_id,
        "name": fund.name,
        "legal_name": fund.legal_name,
        "vintage_year": fund.vintage_year,
        "strategy": fund.strategy,
        "currency_code": fund.currency_code,
        "target_size": fund.target_size,
        "hard_cap": fund.hard_cap,
        "current_size": current_size,
        "status": fund.status,
        "inception_date": fund.inception_date,
        "close_date": fund.close_date,
        "description": fund.description,
        "created_at": fund.created_at,
        "updated_at": fund.updated_at,
    }


def _to_list_item(fund: FundModel, current_size: Decimal) -> dict:
    return {
        "id": fund.id,
        "organization_id": fund.organization_id,
        "fund_group_id": fund.fund_group_id,
        "name": fund.name,
        "currency_code": fund.currency_code,
        "target_size": fund.target_size,
        "current_size": current_size,
        "status": fund.status,
        "vintage_year": fund.vintage_year,
    }


@router.get("", response_model=list[FundListItem])
async def list_funds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = FundRepository(db)
    rows = repo.list_for_membership(membership, skip=skip, limit=limit)
    return [_to_list_item(fund, current_size) for fund, current_size in rows]


@router.get("/{fund_id}", response_model=FundRead)
async def get_fund(
    fund_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = FundRepository(db)
    row = repo.get(fund_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    fund, current_size = row
    if not repo.membership_can_view(membership, fund):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this fund",
        )
    return _to_read_dict(fund, current_size)


@router.get("/{fund_id}/overview", response_model=FundOverview)
async def get_fund_overview(
    fund_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = FundRepository(db)
    row = repo.get(fund_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    fund, _ = row
    if not repo.membership_can_view(membership, fund):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this fund",
        )
    committed, called, distributed = repo.overview_totals(fund_id)
    return FundOverview(
        fund_id=fund.id,  # type: ignore[invalid-argument-type]
        currency_code=fund.currency_code,  # type: ignore[invalid-argument-type]
        committed=committed,
        called=called,
        distributed=distributed,
        remaining_commitment=committed - called,
        irr=None,
    )


@router.post("", response_model=FundRead, status_code=status.HTTP_201_CREATED)
async def create_fund(
    data: FundCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    payload = data.model_dump()
    payload["organization_id"] = membership.organization_id
    repo = FundRepository(db)
    fund, current_size = repo.create(FundCreate(**payload))
    return _to_read_dict(fund, current_size)


@router.patch("/{fund_id}", response_model=FundRead)
async def update_fund(
    fund_id: int,
    data: FundUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = FundRepository(db)
    row = repo.get(fund_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    fund, _ = row
    if fund.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit funds outside your organization",
        )
    updated = repo.update(fund_id, data)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    fund, current_size = updated
    return _to_read_dict(fund, current_size)


@router.post("/{fund_id}/archive", response_model=FundRead)
async def archive_fund(
    fund_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = FundRepository(db)
    row = repo.get(fund_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    fund, _ = row
    if fund.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot archive funds outside your organization",
        )
    archived = repo.archive(fund_id)
    if archived is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    fund, current_size = archived
    return _to_read_dict(fund, current_size)
