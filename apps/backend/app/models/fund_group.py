import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class FundGroup(Base):
    __tablename__ = "fund_groups"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by_user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="fund_groups")
    created_by_user = relationship("User", back_populates="created_fund_groups")
    funds = relationship("Fund", back_populates="fund_group")
