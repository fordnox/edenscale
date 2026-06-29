from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class InvestorContact(Base):
    __tablename__ = "investor_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investor_id = Column(
        Integer, ForeignKey("investors.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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
