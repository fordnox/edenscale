"""The investor portal's API surface, mounted under ``/investor``.

Structural counterpart of the manager endpoints: every route here resolves
access via ``get_investor_membership`` (contact links, transient ``lp``
membership — see ``app.core.investor_access``) and delegates to the existing
handlers, so the scoping logic stays in one place. Routes in this namespace
are LP-scoped by construction — org-role users get their personal investor
view here, never the org-wide one.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.investor_access import get_investor_membership
from app.core.rbac import get_current_user_record
from app.models.enums import (
    CapitalCallStatus,
    CommunicationType,
    DistributionStatus,
    DocumentType,
)
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.investor_contact_repository import InvestorContactRepository
from app.routers import (
    capital_calls,
    commitments,
    communications,
    distributions,
    documents,
    funds,
    investor_contacts,
    investors,
)
from app.schemas.capital_call import CapitalCallRead
from app.schemas.commitment import CommitmentRead
from app.schemas.communication import CommunicationRead, CommunicationRecipientRead
from app.schemas.dashboard import DashboardOverviewResponse
from app.schemas.distribution import DistributionRead
from app.schemas.document import DocumentRead
from app.schemas.fund import FundListItem, FundOverview, FundRead
from app.schemas.investor import InvestorListItem
from app.schemas.investor_contact import InvestorContactRead
from app.schemas.investor_portal import InvestorOrganizationRead

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/organizations", response_model=list[InvestorOrganizationRead])
def list_investor_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    """Organizations the caller can enter as an investor (via contact links).
    Deliberately membership-free: this is the portal's org switcher source."""
    repo = InvestorContactRepository(db)
    organizations = repo.investor_organizations_for_user(
        current_user.id,  # type: ignore[invalid-argument-type]
    )
    return [{"organization_id": org.id, "organization": org} for org in organizations]


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return DashboardRepository(db).get_overview_for_membership(membership)


@router.get("/funds", response_model=list[FundListItem])
def list_funds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return funds.list_funds(skip=skip, limit=limit, db=db, membership=membership)


@router.get("/funds/by-slug/{slug}", response_model=FundRead)
def get_fund_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return funds.get_fund_by_slug(slug=slug, db=db, membership=membership)


@router.get("/funds/{fund_id}", response_model=FundRead)
def get_fund(
    fund_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return funds.get_fund(fund_id=fund_id, db=db, membership=membership)


@router.get("/funds/{fund_id}/overview", response_model=FundOverview)
def get_fund_overview(
    fund_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return funds.get_fund_overview(fund_id=fund_id, db=db, membership=membership)


@router.get("/commitments", response_model=list[CommitmentRead])
def list_commitments(
    fund_id: uuid.UUID | None = None,
    investor_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return commitments.list_commitments(
        fund_id=fund_id,
        investor_id=investor_id,
        skip=skip,
        limit=limit,
        db=db,
        membership=membership,
    )


@router.get("/capital-calls", response_model=list[CapitalCallRead])
def list_capital_calls(
    fund_id: uuid.UUID | None = None,
    status_filter: CapitalCallStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return capital_calls.list_capital_calls(
        fund_id=fund_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
        db=db,
        membership=membership,
    )


@router.get("/distributions", response_model=list[DistributionRead])
def list_distributions(
    fund_id: uuid.UUID | None = None,
    status_filter: DistributionStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return distributions.list_distributions(
        fund_id=fund_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
        db=db,
        membership=membership,
    )


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(
    fund_id: uuid.UUID | None = None,
    investor_id: uuid.UUID | None = None,
    document_type: DocumentType | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return documents.list_documents(
        organization_id=None,
        fund_id=fund_id,
        investor_id=investor_id,
        document_type=document_type,
        skip=skip,
        limit=limit,
        db=db,
        membership=membership,
    )


@router.get("/communications", response_model=list[CommunicationRead])
def list_communications(
    fund_id: uuid.UUID | None = None,
    type: CommunicationType | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return communications.list_communications(
        fund_id=fund_id,
        type=type,
        skip=skip,
        limit=limit,
        db=db,
        membership=membership,
    )


@router.post(
    "/communications/{communication_id}/recipients/{recipient_id}/read",
    response_model=CommunicationRecipientRead,
)
def mark_recipient_read(
    communication_id: uuid.UUID,
    recipient_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return communications.mark_recipient_read(
        communication_id=communication_id,
        recipient_id=recipient_id,
        db=db,
        membership=membership,
    )


@router.get("/investors", response_model=list[InvestorListItem])
def list_investors(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return investors.list_investors(
        skip=skip, limit=limit, db=db, membership=membership
    )


@router.get(
    "/investors/{investor_id}/contacts",
    response_model=list[InvestorContactRead],
)
def list_investor_contacts(
    investor_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_investor_membership),
):
    return investor_contacts.list_investor_contacts(
        investor_id=investor_id,
        skip=skip,
        limit=limit,
        db=db,
        membership=membership,
    )
