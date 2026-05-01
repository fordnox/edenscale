"""Invitation routes for org admins (and superadmins) plus the accept flow.

Mounted under ``/invitations`` (see ``app.main``) behind
``Depends(get_current_user)``. Per-route dependencies handle membership /
superadmin / signed-in checks.

Authorization model:

* ``POST /``, ``GET /``, ``POST /{id}/revoke``, ``POST /{id}/resend`` —
  caller must be acting through an admin or superadmin membership (the
  active membership is resolved from ``X-Organization-Id`` via
  ``get_active_membership``). Non-superadmins additionally must be acting on
  their own organization; superadmins may act on any.
* ``POST /accept`` and ``GET /pending-for-me`` — any authenticated user
  resolved through ``get_current_user_record``. The accept flow validates
  that the invitation email matches the signed-in user.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import (
    get_current_user_record,
    require_membership_roles,
)
from app.models.enums import InvitationStatus, UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.organization_invitation_repository import (
    OrganizationInvitationRepository,
)
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.schemas.organization_invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationListItem,
    InvitationRead,
)
from app.schemas.user_organization_membership import MembershipRead
from app.services.hanko import send_invitation_email

router = APIRouter()


def _build_accept_url(token: str) -> str:
    base = settings.APP_DOMAIN_URL.rstrip("/")
    return f"{base}/invitations/accept?token={token}"


def _ensure_can_act_on_org(
    membership: UserOrganizationMembership, organization_id: int
) -> None:
    """Refuse cross-org actions for non-superadmin callers."""
    if membership.role is UserRole.superadmin:
        return
    if membership.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot act on invitations outside your organization",
        )


def _inviter_user_id(membership: UserOrganizationMembership) -> int | None:
    # Synthesized superadmin memberships have no row id; the FK on the
    # invitation is nullable, so record None and rely on `invited_by_user_id`
    # for the persisted-membership case.
    if membership.id is None:
        return None
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
        require_membership_roles(UserRole.admin, UserRole.superadmin)
    ),
):
    _ensure_can_act_on_org(membership, data.organization_id)

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

    await send_invitation_email(
        email=invitation.email,  # type: ignore[invalid-argument-type]
        accept_url=_build_accept_url(invitation.token),  # type: ignore[invalid-argument-type]
        organization_name=organization.name,  # type: ignore[invalid-argument-type]
    )
    return InvitationRead.model_validate(invitation)


@router.get("", response_model=list[InvitationListItem])
async def list_invitations(
    status_filter: InvitationStatus | None = None,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.superadmin)
    ),
):
    repo = OrganizationInvitationRepository(db)
    return repo.list_for_organization(
        membership.organization_id,  # type: ignore[invalid-argument-type]
        status=status_filter,
    )


@router.get("/pending-for-me", response_model=list[InvitationRead])
async def list_pending_for_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    if not current_user.email:
        return []
    repo = OrganizationInvitationRepository(db)
    invitations = repo.list_pending_for_email(current_user.email.lower())
    return [InvitationRead.model_validate(inv) for inv in invitations]


@router.post("/accept", response_model=MembershipRead)
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
    # SQLite returns naive datetimes; treat them as UTC for comparison.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if invitation.status is InvitationStatus.expired or (
        expires_at is not None and expires_at < now
    ):
        if invitation.status is not InvitationStatus.expired:
            invitation.status = InvitationStatus.expired
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation has expired",
        )

    membership_repo = UserOrganizationMembershipRepository(db)
    existing = membership_repo.get(
        current_user.id,  # type: ignore[invalid-argument-type]
        invitation.organization_id,  # type: ignore[invalid-argument-type]
    )
    if existing is not None:
        if existing.role != invitation.role:
            existing.role = invitation.role
            db.commit()
            db.refresh(existing)
        new_membership = existing
    else:
        new_membership = membership_repo.create(
            user_id=current_user.id,  # type: ignore[invalid-argument-type]
            organization_id=invitation.organization_id,  # type: ignore[invalid-argument-type]
            role=invitation.role,  # type: ignore[invalid-argument-type]
        )

    repo.mark_accepted(invitation.id)  # type: ignore[invalid-argument-type]
    return MembershipRead.model_validate(new_membership)


@router.post("/{invitation_id}/revoke", response_model=InvitationRead)
async def revoke_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.superadmin)
    ),
):
    repo = OrganizationInvitationRepository(db)
    invitation = repo.get(invitation_id)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )
    _ensure_can_act_on_org(membership, invitation.organization_id)  # type: ignore[invalid-argument-type]

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
    invitation_id: int,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.superadmin)
    ),
):
    repo = OrganizationInvitationRepository(db)
    invitation = repo.get(invitation_id)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found"
        )
    _ensure_can_act_on_org(membership, invitation.organization_id)  # type: ignore[invalid-argument-type]

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

    await send_invitation_email(
        email=rotated.email,  # type: ignore[invalid-argument-type]
        accept_url=_build_accept_url(rotated.token),  # type: ignore[invalid-argument-type]
        organization_name=organization.name,  # type: ignore[invalid-argument-type]
    )
    return InvitationRead.model_validate(rotated)
