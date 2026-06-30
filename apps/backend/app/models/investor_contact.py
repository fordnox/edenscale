import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class InvestorContact(Base):
    __tablename__ = "investor_contacts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id = Column(
        Uuid(as_uuid=True), ForeignKey("investors.id"), nullable=False, index=True
    )
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    title = Column(String(150), nullable=True)
    is_primary = Column(Boolean, nullable=True, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    investor = relationship("Investor", back_populates="contacts")
    user = relationship("User", back_populates="investor_contacts")
    communication_recipients = relationship(
        "CommunicationRecipient", back_populates="investor_contact"
    )
