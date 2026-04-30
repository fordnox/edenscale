from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.commitment import Commitment
from app.models.distribution_item import DistributionItem
from app.models.enums import CommitmentStatus, DistributionStatus, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.distribution_repository import DistributionRepository
from app.schemas.distribution import (
    DistributionCreate,
    DistributionItemBulkCreate,
    DistributionItemRead,
    DistributionItemUpdate,
    DistributionRead,
    DistributionUpdate,
)
from app.services.allocation import allocate_pro_rata
from app.services.notification_service import notify

router = APIRouter()


def _load_fund(db: Session, fund_id: int) -> Fund | None:
    return db.query(Fund).filter(Fund.id == fund_id).first()


def _ensure_org_scope(membership: UserOrganizationMembership, fund: Fund) -> None:
    if fund.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage distributions for funds outside your organization",
        )


@router.get("", response_model=list[DistributionRead])
async def list_distributions(
    fund_id: int | None = None,
    status_filter: DistributionStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = DistributionRepository(db)
    return repo.list_for_membership(
        membership,
        fund_id=fund_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get("/{distribution_id}", response_model=DistributionRead)
async def get_distribution(
    distribution_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = DistributionRepository(db)
    distribution = repo.get_with_items(distribution_id)
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found"
        )
    if not repo.membership_can_view(membership, distribution):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this distribution",
        )
    return distribution


@router.post("", response_model=DistributionRead, status_code=status.HTTP_201_CREATED)
async def create_distribution(
    data: DistributionCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    fund = _load_fund(db, data.fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    _ensure_org_scope(membership, fund)
    repo = DistributionRepository(db)
    distribution = repo.create_draft(data, created_by_user_id=membership.user_id)  # type: ignore[invalid-argument-type]
    refreshed = repo.get_with_items(distribution.id)  # type: ignore[invalid-argument-type]
    assert refreshed is not None
    return refreshed


@router.patch("/{distribution_id}", response_model=DistributionRead)
async def update_distribution(
    distribution_id: int,
    data: DistributionUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = DistributionRepository(db)
    distribution = repo.get_with_items(distribution_id)
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found"
        )
    fund = _load_fund(db, distribution.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    updated = repo.update(distribution_id, data)
    assert updated is not None
    return updated


@router.post(
    "/{distribution_id}/items",
    response_model=list[DistributionItemRead],
    status_code=status.HTTP_201_CREATED,
)
async def add_distribution_items(
    distribution_id: int,
    payload: DistributionItemBulkCreate,
    mode: Literal["manual", "pro-rata"] = Query("manual"),
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = DistributionRepository(db)
    distribution = repo.get_with_items(distribution_id)
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found"
        )
    fund = _load_fund(db, distribution.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    allocations: list[tuple[int, Decimal]]
    if mode == "pro-rata":
        approved = (
            db.query(Commitment)
            .filter(
                Commitment.fund_id == distribution.fund_id,
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
            shares = allocate_pro_rata(distribution.amount, approved)  # type: ignore[invalid-argument-type]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        allocations = [(int(c.id), amount) for c, amount in shares]  # type: ignore[invalid-argument-type]
    else:
        allocations = [(item.commitment_id, item.amount_due) for item in payload.items]
    try:
        return repo.add_items(distribution_id, allocations)
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
    "/{distribution_id}/items/{item_id}",
    response_model=DistributionItemRead,
)
async def update_distribution_item(
    distribution_id: int,
    item_id: int,
    data: DistributionItemUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = DistributionRepository(db)
    distribution = repo.get_with_items(distribution_id)
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found"
        )
    fund = _load_fund(db, distribution.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    item = next((i for i in distribution.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Distribution item not found",
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


@router.post("/{distribution_id}/send", response_model=DistributionRead)
async def send_distribution(
    distribution_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = DistributionRepository(db)
    distribution = repo.get_with_items(distribution_id)
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found"
        )
    fund = _load_fund(db, distribution.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    try:
        sent = repo.send(distribution_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert sent is not None
    user_ids = (
        db.query(InvestorContact.user_id)
        .join(Commitment, Commitment.investor_id == InvestorContact.investor_id)
        .join(DistributionItem, DistributionItem.commitment_id == Commitment.id)
        .filter(
            DistributionItem.distribution_id == sent.id,
            InvestorContact.is_primary.is_(True),
            InvestorContact.user_id.is_not(None),
        )
        .distinct()
        .all()
    )
    for (user_id,) in user_ids:
        notify(
            db,
            user_id=user_id,
            title=f"Distribution: {sent.title}",
            message=f"A distribution for {sent.title} has been issued.",
            related_type="distribution",
            related_id=sent.id,  # type: ignore[invalid-argument-type]
        )
    return sent


@router.post("/{distribution_id}/cancel", response_model=DistributionRead)
async def cancel_distribution(
    distribution_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = DistributionRepository(db)
    distribution = repo.get_with_items(distribution_id)
    if distribution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found"
        )
    fund = _load_fund(db, distribution.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    try:
        cancelled = repo.cancel(distribution_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert cancelled is not None
    return cancelled


fund_distributions_router = APIRouter()


@fund_distributions_router.get(
    "/{fund_id}/distributions", response_model=list[DistributionRead]
)
async def list_distributions_for_fund(
    fund_id: int,
    status_filter: DistributionStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    fund = _load_fund(db, fund_id)
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    repo = DistributionRepository(db)
    return repo.list_for_membership(
        membership,
        fund_id=fund_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )
