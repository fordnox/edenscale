import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.enums import UserRole
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.fund_repository import FundRepository
from app.repositories.fund_valuation_repository import FundValuationRepository
from app.schemas.fund_valuation import FundValuationCreate, FundValuationRead

router = APIRouter(dependencies=[Depends(get_current_user)])


def _load_viewable_fund(
    db: Session, fund_id: uuid.UUID, membership: UserOrganizationMembership
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
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view this fund"
        )
    return fund


@router.get("/{fund_id}/valuations", response_model=list[FundValuationRead])
async def list_fund_valuations(
    fund_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    """NAV marks for a fund, newest first. Any member who can view the fund
    (LPs included) can read them — the NAV drives their fair-value figures."""
    _load_viewable_fund(db, fund_id, membership)
    return FundValuationRepository(db).list_for_fund(fund_id)


@router.post(
    "/{fund_id}/valuations",
    response_model=FundValuationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_fund_valuation(
    fund_id: uuid.UUID,
    data: FundValuationCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    """Record (or overwrite) the fund NAV for a given as-of date. Managers only."""
    _load_viewable_fund(db, fund_id, membership)
    return FundValuationRepository(db).upsert(
        fund_id=fund_id,
        data=data,
        created_by_user_id=membership.user_id,  # type: ignore[invalid-argument-type]
    )


@router.delete(
    "/{fund_id}/valuations/{valuation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_fund_valuation(
    fund_id: uuid.UUID,
    valuation_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    _load_viewable_fund(db, fund_id, membership)
    repo = FundValuationRepository(db)
    valuation = repo.get(valuation_id)
    if valuation is None or valuation.fund_id != fund_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Valuation not found"
        )
    repo.delete(valuation_id)
