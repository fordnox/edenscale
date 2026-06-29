from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import DocumentType


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=True, index=True)
    investor_id = Column(Integer, ForeignKey("investors.id"), nullable=True, index=True)
    uploaded_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    document_type = Column(Enum(DocumentType, name="document_type"), nullable=False)
    title = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    is_confidential = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="documents")
    fund = relationship("Fund", back_populates="documents")
    investor = relationship("Investor", back_populates="documents")
    uploaded_by_user = relationship("User", back_populates="uploaded_documents")
