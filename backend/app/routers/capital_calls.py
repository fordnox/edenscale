from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record, require_roles
from app.models.commitment import Commitment
from app.models.enums import CapitalCallStatus, CommitmentStatus, UserRole
from app.models.fund import Fund
from app.models.user import User
from app.repositories.capital_call_repository import CapitalCallRepository
from app.schemas.capital_call import (
    CapitalCallCreate,
    CapitalCallItemBulkCreate,
    CapitalCallItemRead,
    CapitalCallItemUpdate,
    CapitalCallRead,
    CapitalCallUpdate,
)
from app.services.allocation import allocate_pro_rata

router = APIRouter()


def _load_fund(db: Session, fund_id: int) -> Fund | None:
    return db.query(Fund).filter(Fund.id == fund_id).first()


def _ensure_manager_can_edit(current_user: User, fund: Fund) -> None:
    if (
        current_user.role is UserRole.fund_manager
        and fund.organization_id != current_user.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage capital calls for funds outside your organization",
        )


@router.get("", response_model=list[CapitalCallRead])
async def list_capital_calls(
    fund_id: int | None = None,
    status_filter: CapitalCallStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = CapitalCallRepository(db)
    return repo.list_for_user(
        current_user,
        fund_id=fund_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get("/{call_id}", response_model=CapitalCallRead)
async def get_capital_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = CapitalCallRepository(db)
    call = repo.get_with_items(call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Capital call not found"
        )
    if not repo.user_can_view(current_user, call):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this capital call",
        )
    return call


@router.post("", response_model=CapitalCallRead, status_code=status.HTTP_201_CREATED)
async def create_capital_call(
    data: CapitalCallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    fund = _load_fund(db, data.fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    _ensure_manager_can_edit(current_user, fund)
    repo = CapitalCallRepository(db)
    call = repo.create_draft(data, created_by_user_id=current_user.id)  # type: ignore[invalid-argument-type]
    refreshed = repo.get_with_items(call.id)  # type: ignore[invalid-argument-type]
    assert refreshed is not None
    return refreshed


@router.patch("/{call_id}", response_model=CapitalCallRead)
async def update_capital_call(
    call_id: int,
    data: CapitalCallUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CapitalCallRepository(db)
    call = repo.get_with_items(call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Capital call not found"
        )
    fund = _load_fund(db, call.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    updated = repo.update(call_id, data)
    assert updated is not None
    return updated


@router.post(
    "/{call_id}/items",
    response_model=list[CapitalCallItemRead],
    status_code=status.HTTP_201_CREATED,
)
async def add_capital_call_items(
    call_id: int,
    payload: CapitalCallItemBulkCreate,
    mode: Literal["manual", "pro-rata"] = Query("manual"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CapitalCallRepository(db)
    call = repo.get_with_items(call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Capital call not found"
        )
    fund = _load_fund(db, call.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    allocations: list[tuple[int, Decimal]]
    if mode == "pro-rata":
        approved = (
            db.query(Commitment)
            .filter(
                Commitment.fund_id == call.fund_id,
                Commitment.status == CommitmentStatus.approved,
            )
            .order_by(Commitment.id)
            .all()
        )
        if not approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approved commitments on this fund to allocate",
            )
        try:
            shares = allocate_pro_rata(call.amount, approved)  # type: ignore[invalid-argument-type]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        allocations = [(int(c.id), amount) for c, amount in shares]  # type: ignore[invalid-argument-type]
    else:
        allocations = [(item.commitment_id, item.amount_due) for item in payload.items]
    try:
        return repo.add_items(call_id, allocations)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate allocation for commitment",
        ) from exc


@router.patch(
    "/{call_id}/items/{item_id}",
    response_model=CapitalCallItemRead,
)
async def update_capital_call_item(
    call_id: int,
    item_id: int,
    data: CapitalCallItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CapitalCallRepository(db)
    call = repo.get_with_items(call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Capital call not found"
        )
    fund = _load_fund(db, call.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    item = next((i for i in call.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capital call item not found",
        )
    fields = data.model_dump(exclude_unset=True)
    updated = repo.update_item(
        item_id,
        amount_due=fields.get("amount_due"),
        amount_paid=fields.get("amount_paid"),
        paid_at=fields.get("paid_at"),
        paid_at_set="paid_at" in fields,
        note=fields.get("note"),
        note_set="note" in fields,
    )
    assert updated is not None
    return updated


@router.post("/{call_id}/send", response_model=CapitalCallRead)
async def send_capital_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CapitalCallRepository(db)
    call = repo.get_with_items(call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Capital call not found"
        )
    fund = _load_fund(db, call.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    try:
        sent = repo.send(call_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert sent is not None
    return sent


@router.post("/{call_id}/cancel", response_model=CapitalCallRead)
async def cancel_capital_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.fund_manager)),
):
    repo = CapitalCallRepository(db)
    call = repo.get_with_items(call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Capital call not found"
        )
    fund = _load_fund(db, call.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_manager_can_edit(current_user, fund)
    try:
        cancelled = repo.cancel(call_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert cancelled is not None
    return cancelled


fund_capital_calls_router = APIRouter()


@fund_capital_calls_router.get(
    "/{fund_id}/capital-calls", response_model=list[CapitalCallRead]
)
async def list_capital_calls_for_fund(
    fund_id: int,
    status_filter: CapitalCallStatus | None = None,
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
    repo = CapitalCallRepository(db)
    return repo.list_for_user(
        current_user,
        fund_id=fund_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
