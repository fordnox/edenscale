from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record, require_roles
from app.models.enums import UserRole
from app.models.investor import Investor as InvestorModel
from app.models.user import User
from app.repositories.investor_repository import InvestorRepository
from app.schemas.investor import (
    InvestorCreate,
    InvestorListItem,
    InvestorRead,
    InvestorUpdate,
)

router = APIRouter()


def _to_read_dict(
    investor: InvestorModel, total_committed: Decimal, fund_count: int
) -> dict:
    return {
        "id": investor.id,
        "organization_id": investor.organization_id,
        "investor_code": investor.investor_code,
        "name": investor.name,
        "investor_type": investor.investor_type,
        "accredited": investor.accredited,
        "notes": investor.notes,
        "total_committed": total_committed,
        "fund_count": fund_count,
        "created_at": investor.created_at,
        "updated_at": investor.updated_at,
    }


def _to_list_item(
    investor: InvestorModel, total_committed: Decimal, fund_count: int
) -> dict:
    return {
        "id": investor.id,
        "organization_id": investor.organization_id,
        "investor_code": investor.investor_code,
        "name": investor.name,
        "investor_type": investor.investor_type,
        "accredited": investor.accredited,
        "total_committed": total_committed,
        "fund_count": fund_count,
    }


@router.get("", response_model=list[InvestorListItem])
async def list_investors(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = InvestorRepository(db)
    rows = repo.list_for_user(current_user, skip=skip, limit=limit)
    return [
        _to_list_item(investor, total_committed, fund_count)
        for investor, total_committed, fund_count in rows
    ]


@router.get("/{investor_id}", response_model=InvestorRead)
async def get_investor(
    investor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = InvestorRepository(db)
    row = repo.get(investor_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    investor, total_committed, fund_count = row
    if not repo.user_can_view(current_user, investor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this investor",
        )
    return _to_read_dict(investor, total_committed, fund_count)


@router.post("", response_model=InvestorRead, status_code=status.HTTP_201_CREATED)
async def create_investor(
    data: InvestorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    payload = data.model_dump()
    if current_user.role is UserRole.fund_manager:
        if current_user.organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fund managers must belong to an organization to create investors",
            )
        payload["organization_id"] = current_user.organization_id
    elif payload.get("organization_id") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization_id is required",
        )
    repo = InvestorRepository(db)
    investor, total_committed, fund_count = repo.create(InvestorCreate(**payload))
    return _to_read_dict(investor, total_committed, fund_count)


@router.patch("/{investor_id}", response_model=InvestorRead)
async def update_investor(
    investor_id: int,
    data: InvestorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = InvestorRepository(db)
    row = repo.get(investor_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    investor, _, _ = row
    if (
        current_user.role is UserRole.fund_manager
        and investor.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit investors outside your organization",
        )
    updated = repo.update(investor_id, data)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    investor, total_committed, fund_count = updated
    return _to_read_dict(investor, total_committed, fund_count)


@router.delete("/{investor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_investor(
    investor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = InvestorRepository(db)
    row = repo.get(investor_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    investor, _, _ = row
    if (
        current_user.role is UserRole.fund_manager
        and investor.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete investors outside your organization",
        )
    if repo.has_commitments(investor_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete investor with existing commitments",
        )
    repo.delete(investor_id)
    return None
