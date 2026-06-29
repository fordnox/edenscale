from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.communication import Communication
from app.models.enums import CommunicationType, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.communication_repository import CommunicationRepository
from app.schemas.communication import (
    CommunicationCreate,
    CommunicationRead,
    CommunicationRecipientRead,
    CommunicationSendRequest,
    CommunicationUpdate,
)
from app.services.notification_service import notify

router = APIRouter()


def _ensure_can_attach_fund(
    membership: UserOrganizationMembership, db: Session, fund_id: int
) -> Fund:
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    if fund.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot attach communication to a fund outside your organization",
        )
    return fund


def _ensure_can_manage(
    repo: CommunicationRepository,
    membership: UserOrganizationMembership,
    communication: Communication,
) -> None:
    if not repo.membership_can_manage(membership, communication):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage this communication",
        )


@router.get("", response_model=list[CommunicationRead])
async def list_communications(
    fund_id: int | None = None,
    type: CommunicationType | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = CommunicationRepository(db)
    return repo.list_for_membership(
        membership,
        fund_id=fund_id,
        comm_type=type,
        skip=skip,
        limit=limit,
    )


@router.get("/{communication_id}", response_model=CommunicationRead)
async def get_communication(
    communication_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = CommunicationRepository(db)
    communication = repo.get(communication_id)
    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found"
        )
    if not repo.membership_can_view(membership, communication):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this communication",
        )
    return communication


@router.post("", response_model=CommunicationRead, status_code=status.HTTP_201_CREATED)
async def create_communication(
    data: CommunicationCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    if data.fund_id is not None:
        _ensure_can_attach_fund(membership, db, data.fund_id)
    repo = CommunicationRepository(db)
    communication = repo.create_draft(data, sender_user_id=membership.user_id)  # type: ignore[invalid-argument-type]
    return repo.get(communication.id)  # type: ignore[invalid-argument-type]


@router.patch("/{communication_id}", response_model=CommunicationRead)
async def update_communication(
    communication_id: int,
    data: CommunicationUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = CommunicationRepository(db)
    communication = repo.get(communication_id)
    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found"
        )
    _ensure_can_manage(repo, membership, communication)
    if data.fund_id is not None and data.fund_id != communication.fund_id:
        _ensure_can_attach_fund(membership, db, data.fund_id)
    try:
        updated = repo.update(communication_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert updated is not None
    return updated


@router.post("/{communication_id}/send", response_model=CommunicationRead)
async def send_communication(
    communication_id: int,
    payload: CommunicationSendRequest | None = None,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    repo = CommunicationRepository(db)
    communication = repo.get(communication_id)
    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found"
        )
    _ensure_can_manage(repo, membership, communication)
    explicit = payload.recipients if payload is not None else []
    try:
        sent = repo.send(communication_id, explicit_recipients=explicit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    assert sent is not None
    notified: set[int] = set()
    for recipient in sent.recipients:
        target_user_id: int | None = recipient.user_id
        if target_user_id is None and recipient.investor_contact_id is not None:
            contact = (
                db.query(InvestorContact)
                .filter(InvestorContact.id == recipient.investor_contact_id)
                .first()
            )
            target_user_id = contact.user_id if contact is not None else None  # type: ignore[invalid-assignment]
        if target_user_id is None or target_user_id in notified:
            continue
        notified.add(target_user_id)
        notify(
            db,
            user_id=target_user_id,
            title=f"New {sent.type.value}: {sent.subject}",
            message=str(sent.subject),
            related_type="communication",
            related_id=sent.id,  # type: ignore[invalid-argument-type]
        )
    return sent


@router.post(
    "/{communication_id}/recipients/{recipient_id}/read",
    response_model=CommunicationRecipientRead,
)
async def mark_recipient_read(
    communication_id: int,
    recipient_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = CommunicationRepository(db)
    communication = repo.get(communication_id)
    if communication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found"
        )
    recipient = next(
        (r for r in communication.recipients if r.id == recipient_id), None
    )
    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found"
        )
    if membership.role not in (
        UserRole.admin,
        UserRole.fund_manager,
        UserRole.superadmin,
    ):
        is_owner = recipient.user_id == membership.user_id
        is_contact_owner = False
        if not is_owner and recipient.investor_contact_id is not None:
            is_contact_owner = (
                db.query(InvestorContact.id)
                .filter(
                    InvestorContact.id == recipient.investor_contact_id,
                    InvestorContact.user_id == membership.user_id,
                )
                .first()
                is not None
            )
        if not (is_owner or is_contact_owner):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot mark another recipient's row as read",
            )
    updated = repo.mark_recipient_read(communication_id, recipient_id)
    assert updated is not None
    return updated


fund_communications_router = APIRouter()


@fund_communications_router.get(
    "/{fund_id}/communications", response_model=list[CommunicationRead]
)
async def list_communications_for_fund(
    fund_id: int,
    type: CommunicationType | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if fund is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
        )
    repo = CommunicationRepository(db)
    return repo.list_for_membership(
        membership,
        fund_id=fund_id,
        comm_type=type,
        skip=skip,
        limit=limit,
    )
