from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import InvitationStatus, UserRole

INVITATION_EXPIRY_DAYS = 14


def _default_invitation_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False, index=True)
    role = Column(Enum(UserRole, name="invitation_role"), nullable=False)
    token = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(
        Enum(InvitationStatus, name="invitation_status"),
        nullable=False,
        default=InvitationStatus.pending,
    )
    expires_at = Column(DateTime, nullable=False, default=_default_invitation_expiry)
    invited_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="invitations")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])
