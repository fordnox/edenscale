from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    role = Column(Enum(UserRole, name="user_role"), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    title = Column(String(150), nullable=True)
    password_hash = Column(String(255), nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime, nullable=True)
    # Hanko compatibility: indexed external subject id from the Hanko JWT.
    # Nullable so existing rows / non-Hanko users do not require it.
    hanko_subject_id = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="users")
    memberships = relationship(
        "UserOrganizationMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_fund_groups = relationship("FundGroup", back_populates="created_by_user")
    fund_team_memberships = relationship("FundTeamMember", back_populates="user")
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
