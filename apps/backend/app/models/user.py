import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    title = Column(String(150), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime, nullable=True)
    # Hanko compatibility: indexed external subject id from the Hanko JWT.
    # Nullable so existing rows / non-Hanko users do not require it.
    hanko_subject_id = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    memberships = relationship(
        "UserOrganizationMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_fund_groups = relationship("FundGroup", back_populates="created_by_user")
    investor_contacts = relationship("InvestorContact", back_populates="user")
    created_capital_calls = relationship(
        "CapitalCall", back_populates="created_by_user"
    )
    created_distributions = relationship(
        "Distribution", back_populates="created_by_user"
    )
    uploaded_documents = relationship("Document", back_populates="uploaded_by_user")
    sent_communications = relationship("Communication", back_populates="sender_user")
    communication_recipients = relationship(
        "CommunicationRecipient", back_populates="user"
    )
    notifications = relationship("Notification", back_populates="user")
    assigned_tasks = relationship(
        "Task",
        back_populates="assigned_to_user",
        foreign_keys="Task.assigned_to_user_id",
    )
    created_tasks = relationship(
        "Task", back_populates="created_by_user", foreign_keys="Task.created_by_user_id"
    )
    audit_logs = relationship("AuditLog", back_populates="user")

    @property
    def is_superadmin(self) -> bool:
        """Superadmins are defined by ``SUPERADMIN_EMAIL`` in config, never
        stored: a user is a superadmin iff their (Hanko-verified) email is
        listed there. Per-organization roles live on memberships."""
        return (self.email or "").lower() in settings.superadmin_emails
