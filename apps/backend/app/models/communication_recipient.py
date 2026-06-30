import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CommunicationRecipient(Base):
    __tablename__ = "communication_recipients"
    __table_args__ = (
        UniqueConstraint(
            "communication_id", "user_id", name="uq_communication_recipient_comm_user"
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    communication_id = Column(
        Uuid(as_uuid=True), ForeignKey("communications.id"), nullable=False, index=True
    )
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    investor_contact_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("investor_contacts.id"),
        nullable=True,
        index=True,
    )
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    communication = relationship("Communication", back_populates="recipients")
    user = relationship("User", back_populates="communication_recipients")
    investor_contact = relationship(
        "InvestorContact", back_populates="communication_recipients"
    )
