import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import BankPaymentTransactionStatus


class BankPaymentTransaction(Base):
    """One credit line parsed from a bank statement, plus its assignment.

    ``capital_call_item_id`` is the capital-call item this payment settles once
    a manager confirms the match. The ``(import_id, bank_reference)`` unique
    constraint stops the same statement line being ingested twice.
    """

    __tablename__ = "bank_payment_transactions"
    __table_args__ = (
        UniqueConstraint(
            "import_id",
            "bank_reference",
            name="uq_bank_payment_txn_import_reference",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("bank_statement_imports.id"),
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=True)
    value_date = Column(Date, nullable=True)
    debtor_name = Column(String(255), nullable=True)
    debtor_iban = Column(String(50), nullable=True)
    remittance_info = Column(Text, nullable=True)
    bank_reference = Column(String(255), nullable=False)
    capital_call_item_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("capital_call_items.id"),
        nullable=True,
        index=True,
    )
    status = Column(
        Enum(BankPaymentTransactionStatus, name="bank_payment_transaction_status"),
        nullable=False,
        default=BankPaymentTransactionStatus.unmatched,
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    statement_import = relationship(
        "BankStatementImport", back_populates="transactions"
    )
    capital_call_item = relationship("CapitalCallItem")
