import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import UserRole


class UserOrganizationMembership(Base):
    __tablename__ = "user_organization_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_org_membership"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    role = Column(Enum(UserRole, name="membership_role"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")
