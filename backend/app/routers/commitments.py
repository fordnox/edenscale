from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record, require_roles
from app.models.enums import CommitmentStatus, UserRole
from app.models.fund import Fund
from app.models.investor import Investor
from app.models.user import User
from app.repositories.commitment_repository import CommitmentRepository
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentRead,
    CommitmentStatusUpdate,
    CommitmentUpdate,
)

router = APIRouter()


_TERMINAL_STATUSES = {CommitmentStatus.declined, CommitmentStatus.cancelled}


def _load_fund(db: Session, fund_id: int) -> Fund | None:
    return db.query(Fund).filter(Fund.id == fund_id).first()


def _load_investor(db: Session, investor_id: int) -> Investor | None:
    return db.query(Investor).filter(Investor.id == investor_id).first()


def _ensure_manager_can_edit(current_user: User, fund: Fund) -> None:
    if (
        current_user.role is UserRole.fund_manager
        and fund.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage commitments for funds outside your organization",
        )


@router.get("", response_model=list[CommitmentRead])
async def list_commitments(
    fund_id: int | None = None,
    investor_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = CommitmentRepository(db)
    return repo.list(
        current_user,
        fund_id=fund_id,
        investor_id=investor_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{commitment_id}", response_model=CommitmentRead)
async def get_commitment(
    commitment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = CommitmentRepository(db)
    commitment = repo.get(commitment_id)
    if commitment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found"
        )
    if not repo.user_can_view(current_user, commitment):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this commitment",
        )
    return commitment


@router.post("", response_model=CommitmentRead, status_code=status.HTTP_201_CREATED)
async def create_commitment(
    data: CommitmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    fund = _load_fund(db, data.fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    investor = _load_investor(db, data.investor_id)
    if investor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    _ensure_manager_can_edit(current_user, fund)
    repo = CommitmentRepository(db)
    if repo.get_by_fund_and_investor(data.fund_id, data.investor_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Commitment already exists for this fund and investor",
        )
    try:
        return repo.create(data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Commitment already exists for this fund and investor",
        ) from exc


@router.patch("/{commitment_id}", response_model=CommitmentRead)
async def update_commitment(
    commitment_id: int,
    data: CommitmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CommitmentRepository(db)
    commitment = repo.get(commitment_id)
    if commitment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found"
        )
    fund = _load_fund(db, commitment.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    updated = repo.update(commitment_id, data)
    assert updated is not None
    return updated


@router.post("/{commitment_id}/status", response_model=CommitmentRead)
async def update_commitment_status(
    commitment_id: int,
    data: CommitmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CommitmentRepository(db)
    commitment = repo.get(commitment_id)
    if commitment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found"
        )
    fund = _load_fund(db, commitment.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    if commitment.status in _TERMINAL_STATUSES and data.status != commitment.status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition out of terminal status '{commitment.status.value}'",
        )
    updated = repo.set_status(commitment_id, data.status)
    assert updated is not None
    return updated


fund_commitments_router = APIRouter()


@fund_commitments_router.get(
    "/{fund_id}/commitments", response_model=list[CommitmentRead]
)
async def list_commitments_for_fund(
    fund_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    fund = _load_fund(db, fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    repo = CommitmentRepository(db)
    return repo.list(current_user, fund_id=fund_id, skip=skip, limit=limit)


investor_commitments_router = APIRouter()


@investor_commitments_router.get(
    "/{investor_id}/commitments", response_model=list[CommitmentRead]
)
async def list_commitments_for_investor(
    investor_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    investor = _load_investor(db, investor_id)
    if investor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    repo = CommitmentRepository(db)
    return repo.list(current_user, investor_id=investor_id, skip=skip, limit=limit)
