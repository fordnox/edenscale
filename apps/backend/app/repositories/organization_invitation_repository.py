import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import InvitationStatus, UserRole
from app.models.organization_invitation import OrganizationInvitation


def _generate_invitation_token() -> str:
    return secrets.token_urlsafe(48)


class OrganizationInvitationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        organization_id: int,
        email: str,
        role: UserRole,
        invited_by_user_id: int | None,
    ) -> OrganizationInvitation:
        invitation = OrganizationInvitation(
            organization_id=organization_id,
            email=email,
            role=role,
            token=_generate_invitation_token(),
            status=InvitationStatus.pending,
            invited_by_user_id=invited_by_user_id,
        )
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def get(self, invitation_id: int) -> OrganizationInvitation | None:
        return (
            self.db.query(OrganizationInvitation)
            .filter(OrganizationInvitation.id == invitation_id)
            .first()
        )

    def get_by_token(self, token: str) -> OrganizationInvitation | None:
        return (
            self.db.query(OrganizationInvitation)
            .filter(OrganizationInvitation.token == token)
            .first()
        )

    def list_for_organization(
        self,
        organization_id: int,
        *,
        status: InvitationStatus | None = None,
    ) -> list[OrganizationInvitation]:
        query = self.db.query(OrganizationInvitation).filter(
            OrganizationInvitation.organization_id == organization_id
        )
        if status is not None:
            query = query.filter(OrganizationInvitation.status == status)
        return query.order_by(OrganizationInvitation.id.desc()).all()

    def list_pending_for_email(self, email: str) -> list[OrganizationInvitation]:
        return (
            self.db.query(OrganizationInvitation)
            .filter(
                OrganizationInvitation.email == email,
                OrganizationInvitation.status == InvitationStatus.pending,
            )
            .order_by(OrganizationInvitation.id.desc())
            .all()
        )

    def mark_accepted(self, invitation_id: int) -> OrganizationInvitation | None:
        invitation = self.get(invitation_id)
        if invitation is None:
            return None
        invitation.status = InvitationStatus.accepted
        invitation.accepted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def mark_revoked(self, invitation_id: int) -> OrganizationInvitation | None:
        invitation = self.get(invitation_id)
        if invitation is None:
            return None
        invitation.status = InvitationStatus.revoked
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def rotate_token(self, invitation_id: int) -> OrganizationInvitation | None:
        """Issue a new token for a pending invitation, invalidating the old one.

        Used by the resend flow so the prior email's link stops working.
        """
        invitation = self.get(invitation_id)
        if invitation is None:
            return None
        invitation.token = _generate_invitation_token()
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def expire_stale(self, *, now: datetime | None = None) -> int:
        """Flip pending invitations whose `expires_at` is in the past to
        `expired`. Returns the number of rows updated.

        Intended for a future cron — written now so the model + repository
        contract is complete; not yet scheduled.
        """
        cutoff = now or datetime.now(timezone.utc)
        updated = (
            self.db.query(OrganizationInvitation)
            .filter(
                OrganizationInvitation.status == InvitationStatus.pending,
                OrganizationInvitation.expires_at < cutoff,
            )
            .update(
                {OrganizationInvitation.status: InvitationStatus.expired},
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated)
