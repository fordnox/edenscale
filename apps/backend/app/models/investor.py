from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Investor(Base):
    __tablename__ = "investors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
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
