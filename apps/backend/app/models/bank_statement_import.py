import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import BankStatementImportStatus


class BankStatementImport(Base):
    """A single uploaded ISO 20022 statement and the batch of payments in it."""

    __tablename__ = "bank_statement_imports"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    file_name = Column(String(255), nullable=False)
    # Canonical storage URL of the raw XML (kept for audit / re-review).
    storage_url = Column(Text, nullable=True)
    status = Column(
        Enum(BankStatementImportStatus, name="bank_statement_import_status"),
        nullable=False,
        default=BankStatementImportStatus.pending,
    )
    transaction_count = Column(Integer, nullable=False, default=0)
    applied_count = Column(Integer, nullable=False, default=0)
    imported_by_user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")
    imported_by_user = relationship("User")
    transactions = relationship(
        "BankPaymentTransaction",
        back_populates="statement_import",
        cascade="all, delete-orphan",
    )
