import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Investor(Base):
    __tablename__ = "investors"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    investor_code = Column(String(50), nullable=True, unique=True)
    name = Column(String(255), nullable=False)
    investor_type = Column(String(100), nullable=True)
    accredited = Column(Boolean, nullable=True, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="investors")
    contacts = relationship("InvestorContact", back_populates="investor")
    commitments = relationship("Commitment", back_populates="investor")
    documents = relationship("Document", back_populates="investor")
