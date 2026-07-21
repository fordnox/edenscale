"""Invitation routes for organization staff plus the accept flow.

Mounted under ``/invitations`` (see ``app.main``) behind
``Depends(get_current_user)``. Per-route dependencies handle membership /
membership / signed-in checks.

Authorization model:

* ``POST /``, ``GET /``, ``POST /{id}/revoke``, ``POST /{id}/resend`` —
  caller must be acting through an admin or fund_manager
  membership (the active membership is resolved from ``X-Organization-Id``
  via ``get_active_membership``). Fund managers are scoped to limited-partner
  invitations only — they may create/list/revoke/resend invitations whose
  role is ``lp`` but never invitations that would grant manager/admin access.
  The caller must be acting on their own organization.
* ``POST /accept`` and ``GET /pending-for-me`` — any authenticated user
  resolved through ``get_current_user_record``. The accept flow validates
  that the invitation email matches the signed-in user.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import (
    get_current_user_record,
    require_membership_roles,
    require_tenant_user,
)
from app.models.enums import InvitationStatus, UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.investor_contact_repository import InvestorContactRepository
from app.repositories.organization_invitation_repository import (
    OrganizationInvitationRepository,
)
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.schemas.organization_invitation import (
    InvitationAccept,
    InvitationAcceptResponse,
    InvitationCreate,
    InvitationListItem,
    InvitationRead,
)
from app.services.drip import fire_investor_signup
from app.services.hanko import ensure_hanko_user
from app.services.notifications import (
    notify_invitation,
    notify_invitation_accepted,
    notify_welcome,
)

router = APIRouter(
    dependencies=[Depends(get_current_user), Depends(require_tenant_user)]
)


def _ensure_can_act_on_org(
    membership: UserOrganizationMembership, organization_id: uuid.UUID
) -> None:
    """Refuse cross-organization actions."""
    if membership.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot act on invitations outside your organization",
        )


def _ensure_can_manage_invitation_role(
    membership: UserOrganizationMembership, invited_role: UserRole
) -> None:
    """Fund managers may only act on limited-partner invitations. Admins can
    manage any non-superadmin role. Keeps a fund manager from
    minting new managers/admins while still letting them onboard their LPs."""
    if membership.role is UserRole.fund_manager and invited_role is not UserRole.lp:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fund managers can only invite limited partners",
        )


def _inviter_user_id(membership: UserOrganizationMembership) -> uuid.UUID | None:
    return membership.user_id  # type: ignore[invalid-return-type]


@router.post(
    "",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    data: InvitationCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    _ensure_can_act_on_org(membership, data.organization_id)
    _ensure_can_manage_invitation_role(membership, data.role)

    organization = OrganizationRepository(db).get(data.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    repo = OrganizationInvitationRepository(db)
    invitation = repo.create(
        organization_id=data.organization_id,
        email=str(data.email).lower(),
        role=data.role,
        invited_by_user_id=_inviter_user_id(membership),
    )

    # Pre-provision the Hanko account so the invitee can sign in from the
    # invitation link; the email itself is delivered by the worker.
    await ensure_hanko_user(invitation.email)  # type: ignore[invalid-argument-type]
    await notify_invitation(db, invitation=invitation)
    return InvitationRead.model_validate(invitation)


@router.get("", response_model=list[InvitationListItem])
def list_invitations(
    status_filter: InvitationStatus | None = None,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    repo = OrganizationInvitationRepository(db)
    invitations = repo.list_for_organization(
        membership.organization_id,  # type: ignore[invalid-argument-type]
        status=status_filter,
    )
    # Fund managers only see the LP invitations they're allowed to manage.
    if membership.role is UserRole.fund_manager:
        invitations = [i for i in invitations if i.role is UserRole.lp]
    return invitations


@router.get("/pending-for-me", response_model=list[InvitationRead])
def list_pending_for_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    if not current_user.email:
        return []
    repo = OrganizationInvitationRepository(db)
    invitations = repo.list_pending_for_email(current_user.email.lower())
    return [InvitationRead.model_validate(inv) for inv in invitations]


@router.post("/accept", response_model=InvitationAcceptResponse)
async def accept_invitation(
    data: InvitationAccept,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = OrganizationInvitationRepository(db)
    invitation = repo.get_by_token(data.token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )

    invitee_email = invitation.email or ""
    user_email = current_user.email or ""
    if invitee_email.lower() != user_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invitation does not match the signed-in user",
        )

    if invitation.status is InvitationStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation already accepted",
        )
    if invitation.status is InvitationStatus.revoked:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation has been revoked",
        )

    now = datetime.now(timezone.utc)
    expires_at = invitation.expires_at
    # ``expires_at`` is a timezone-less ``DateTime`` column, so it comes back
    # naive; the repo convention stores UTC there. Attach UTC before comparing.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invitation.status is InvitationStatus.expired or (
        expires_at is not None and expires_at < now
    ):
        if invitation.status is not InvitationStatus.expired:
            invitation = repo.mark_expired(invitation.id)  # type: ignore[invalid-argument-type,assignment]
            assert invitation is not None
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation has expired",
        )

    # Investor (lp) invitations never create or touch membership rows: portal
    # access comes from the contact links bound below, and an invitee who is
    # already staff (e.g. an admin who is personally an investor) must keep
    # their staff role. Staff invitations still create/update the membership.
    if invitation.role is not UserRole.lp:
        membership_repo = UserOrganizationMembershipRepository(db)
        existing = membership_repo.get(
            current_user.id,  # type: ignore[invalid-argument-type]
            invitation.organization_id,  # type: ignore[invalid-argument-type]
        )
        if existing is not None:
            if existing.role != invitation.role:
                existing = membership_repo.update_role(existing.id, invitation.role)  # type: ignore[invalid-argument-type,assignment]
                assert existing is not None
        else:
            membership_repo.create(
                user_id=current_user.id,  # type: ignore[invalid-argument-type]
                organization_id=invitation.organization_id,  # type: ignore[invalid-argument-type]
                role=invitation.role,  # type: ignore[invalid-argument-type]
            )

    repo.mark_accepted(invitation.id)  # type: ignore[invalid-argument-type]
    InvestorContactRepository(db).link_unclaimed_by_email(
        invitation.organization_id,  # type: ignore[invalid-argument-type]
        user_email,  # type: ignore[invalid-argument-type]
        current_user.id,  # type: ignore[invalid-argument-type]
    )
    await notify_invitation_accepted(
        db, invitation=invitation, accepted_by=current_user
    )
    if invitation.organization is not None:
        await notify_welcome(
            db, user=current_user, organization=invitation.organization
        )
        # LPs only: the drip walks the reader through the investor portal, which
        # staff never see.
        if invitation.role is UserRole.lp:
            await fire_investor_signup(
                user=current_user, organization=invitation.organization
            )
    return InvitationAcceptResponse(
        organization_id=invitation.organization_id,  # type: ignore[invalid-argument-type]
        role=invitation.role,  # type: ignore[invalid-argument-type]
        organization=invitation.organization,
    )


@router.post("/{invitation_id}/revoke", response_model=InvitationRead)
def revoke_invitation(
    invitation_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    repo = OrganizationInvitationRepository(db)
    invitation = repo.get(invitation_id)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )
    _ensure_can_act_on_org(membership, invitation.organization_id)  # type: ignore[invalid-argument-type]
    _ensure_can_manage_invitation_role(membership, invitation.role)  # type: ignore[invalid-argument-type]

    if invitation.status is not InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot revoke invitation in status {invitation.status.value}",
        )

    revoked = repo.mark_revoked(invitation_id)
    assert revoked is not None
    return InvitationRead.model_validate(revoked)


@router.post("/{invitation_id}/resend", response_model=InvitationRead)
async def resend_invitation(
    invitation_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    repo = OrganizationInvitationRepository(db)
    invitation = repo.get(invitation_id)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )
    _ensure_can_act_on_org(membership, invitation.organization_id)  # type: ignore[invalid-argument-type]
    _ensure_can_manage_invitation_role(membership, invitation.role)  # type: ignore[invalid-argument-type]

    if invitation.status is not InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot resend invitation in status {invitation.status.value}",
        )

    organization = OrganizationRepository(db).get(invitation.organization_id)  # type: ignore[invalid-argument-type]
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    rotated = repo.rotate_token(invitation_id)
    assert rotated is not None

    await ensure_hanko_user(rotated.email)  # type: ignore[invalid-argument-type]
    await notify_invitation(db, invitation=rotated)
    return InvitationRead.model_validate(rotated)
