from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import OrganizationType


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(OrganizationType, name="organization_type"), nullable=False)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    tax_id = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="organization")
    memberships = relationship(
        "UserOrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    fund_groups = relationship("FundGroup", back_populates="organization")
    funds = relationship("Fund", back_populates="organization")
    investors = relationship("Investor", back_populates="organization")
    documents = relationship("Document", back_populates="organization")
    audit_logs = relationship("AuditLog", back_populates="organization")
    invitations = relationship(
        "OrganizationInvitation",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
