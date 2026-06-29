from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.enums import UserRole
from app.models.investor import Investor
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.investor_contact_repository import InvestorContactRepository
from app.repositories.investor_repository import InvestorRepository
from app.schemas.investor_contact import (
    InvestorContactCreate,
    InvestorContactRead,
    InvestorContactUpdate,
)

router = APIRouter()

_ORG_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


def _load_investor_or_404(db: Session, investor_id: int) -> Investor:
    repo = InvestorRepository(db)
    row = repo.get(investor_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
        )
    return row[0]


def _ensure_org_scope(
    membership: UserOrganizationMembership, investor: Investor
) -> None:
    if investor.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage contacts for investors outside your organization",
        )


@router.get("/{investor_id}/contacts", response_model=list[InvestorContactRead])
async def list_investor_contacts(
    investor_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    investor = _load_investor_or_404(db, investor_id)
    repo = InvestorContactRepository(db)
    if membership.role in _ORG_ROLES:
        if investor.organization_id != membership.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view contacts for investors outside your organization",
            )
        return repo.list_for_investor(investor_id, skip=skip, limit=limit)
    own_contacts = repo.list_for_user_and_investor(investor_id, membership.user_id)  # type: ignore[invalid-argument-type]
    if not own_contacts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view contacts for this investor",
        )
    return own_contacts


@router.post(
    "/{investor_id}/contacts",
    response_model=InvestorContactRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_investor_contact(
    investor_id: int,
    data: InvestorContactCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    investor = _load_investor_or_404(db, investor_id)
    _ensure_org_scope(membership, investor)
    repo = InvestorContactRepository(db)
    return repo.create(investor_id, data)


@router.patch(
    "/{investor_id}/contacts/{contact_id}",
    response_model=InvestorContactRead,
)
async def update_investor_contact(
    investor_id: int,
    contact_id: int,
    data: InvestorContactUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    investor = _load_investor_or_404(db, investor_id)
    _ensure_org_scope(membership, investor)
    repo = InvestorContactRepository(db)
    contact = repo.get(contact_id)
    if contact is None or contact.investor_id != investor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    updated = repo.update(contact_id, data)
    assert updated is not None
    return updated


@router.delete(
    "/{investor_id}/contacts/{contact_id}",
    response_model=InvestorContactRead,
)
async def delete_investor_contact(
    investor_id: int,
    contact_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
    ),
):
    investor = _load_investor_or_404(db, investor_id)
    _ensure_org_scope(membership, investor)
    repo = InvestorContactRepository(db)
    contact = repo.get(contact_id)
    if contact is None or contact.investor_id != investor_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    deleted = repo.delete(contact_id)
    assert deleted is not None
    return deleted
