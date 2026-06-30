import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import CommunicationType


class Communication(Base):
    __tablename__ = "communications"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id = Column(
        Uuid(as_uuid=True), ForeignKey("funds.id"), nullable=True, index=True
    )
    sender_user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    type = Column(Enum(CommunicationType, name="communication_type"), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fund = relationship("Fund", back_populates="communications")
    sender_user = relationship("User", back_populates="sent_communications")
    recipients = relationship("CommunicationRecipient", back_populates="communication")
