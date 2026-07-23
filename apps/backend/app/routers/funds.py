import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
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
from app.services.metrics import (
    FundMetrics,
    fund_metrics,
    fund_metrics_bulk,
    latest_fund_nav,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


def _to_read_dict(
    fund: FundModel, current_size: Decimal, nav: Decimal | None = None
) -> dict:
    return {
        "id": fund.id,
        "organization_id": fund.organization_id,
        "fund_group_id": fund.fund_group_id,
        "name": fund.name,
        "slug": fund.slug,
        "legal_name": fund.legal_name,
        "vintage_year": fund.vintage_year,
        "strategy": fund.strategy,
        "currency_code": fund.currency_code,
        "target_size": fund.target_size,
        "hard_cap": fund.hard_cap,
        "current_size": current_size,
        "nav": nav,
        "status": fund.status,
        "inception_date": fund.inception_date,
        "close_date": fund.close_date,
        "description": fund.description,
        "website_url": fund.website_url,
        "created_at": fund.created_at,
        "updated_at": fund.updated_at,
    }


def _to_list_item(
    fund: FundModel, current_size: Decimal, metrics: FundMetrics | None = None
) -> dict:
    return {
        "id": fund.id,
        "organization_id": fund.organization_id,
        "fund_group_id": fund.fund_group_id,
        "name": fund.name,
        "slug": fund.slug,
        "currency_code": fund.currency_code,
        "target_size": fund.target_size,
        "current_size": current_size,
        "nav": metrics.nav if metrics else None,
        "dpi": metrics.dpi if metrics else None,
        "tvpi": metrics.tvpi if metrics else None,
        "irr": metrics.irr if metrics else None,
        "status": fund.status,
        "vintage_year": fund.vintage_year,
    }


@router.get("", response_model=list[FundListItem])
def list_funds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = FundRepository(db)
    rows = repo.list_for_membership(membership, skip=skip, limit=limit)
    metrics = fund_metrics_bulk(db, [fund.id for fund, _ in rows])  # type: ignore[invalid-argument-type]
    return [
        _to_list_item(fund, current_size, metrics.get(fund.id))  # type: ignore[invalid-argument-type]
        for fund, current_size in rows
    ]


@router.get("/by-slug/{slug}", response_model=FundRead)
def get_fund_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    """Resolve a fund from its slug within the caller's active organization.

    Declared before ``/{fund_id}`` so the literal ``by-slug`` prefix wins the
    route match instead of being parsed as a fund UUID.
    """
    repo = FundRepository(db)
    row = repo.get_by_slug(membership.organization_id, slug)  # type: ignore[invalid-argument-type]
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
    return _to_read_dict(fund, current_size, latest_fund_nav(db, fund.id))  # type: ignore[invalid-argument-type]


@router.get("/{fund_id}", response_model=FundRead)
def get_fund(
    fund_id: uuid.UUID,
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
    return _to_read_dict(fund, current_size, latest_fund_nav(db, fund.id))  # type: ignore[invalid-argument-type]


@router.get("/{fund_id}/overview", response_model=FundOverview)
def get_fund_overview(
    fund_id: uuid.UUID,
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
    metrics = fund_metrics(db, fund_id)
    return FundOverview(
        fund_id=fund.id,  # type: ignore[invalid-argument-type]
        currency_code=fund.currency_code,  # type: ignore[invalid-argument-type]
        committed=metrics.committed,
        called=metrics.called,
        distributed=metrics.distributed,
        remaining_commitment=metrics.committed - metrics.called,
        nav=metrics.nav,
        irr=metrics.irr,
        dpi=metrics.dpi,
        tvpi=metrics.tvpi,
        rvpi=metrics.rvpi,
        called_pct=metrics.called_pct,
    )


@router.post("", response_model=FundRead, status_code=status.HTTP_201_CREATED)
def create_fund(
    data: FundCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    payload = data.model_dump()
    payload["organization_id"] = membership.organization_id
    repo = FundRepository(db)
    fund, current_size = repo.create(FundCreate(**payload))
    return _to_read_dict(fund, current_size)


@router.patch("/{fund_id}", response_model=FundRead)
def update_fund(
    fund_id: uuid.UUID,
    data: FundUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
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
def archive_fund(
    fund_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
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
