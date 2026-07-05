from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    BankPaymentTransactionStatus,
    BankStatementImportStatus,
)

Confidence = Literal["high", "medium", "low"]


class MatchCandidate(BaseModel):
    """A suggested capital-call item a bank transaction could settle."""

    capital_call_item_id: UUID4
    capital_call_id: UUID4
    capital_call_title: str
    fund_id: UUID4
    fund_name: str
    currency_code: str
    investor_id: UUID4
    investor_name: str
    amount_due: Decimal
    amount_paid: Decimal
    remaining: Decimal
    score: float
    confidence: Confidence
    currency_mismatch: bool


class BankTransactionRead(BaseModel):
    id: UUID4
    import_id: UUID4
    amount: Decimal
    currency: str | None
    value_date: date | None
    debtor_name: str | None
    debtor_iban: str | None
    remittance_info: str | None
    bank_reference: str
    capital_call_item_id: UUID4 | None
    status: BankPaymentTransactionStatus
    created_at: datetime | None
    updated_at: datetime | None
    # Suggested matches — computed at parse time, not persisted.
    candidates: list[MatchCandidate] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BankImportRead(BaseModel):
    id: UUID4
    organization_id: UUID4
    file_name: str
    status: BankStatementImportStatus
    transaction_count: int
    applied_count: int
    imported_by_user_id: UUID4 | None
    created_at: datetime | None
    updated_at: datetime | None
    transactions: list[BankTransactionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BankImportListItem(BaseModel):
    """Lightweight row for the import-history list (no transactions)."""

    id: UUID4
    organization_id: UUID4
    file_name: str
    status: BankStatementImportStatus
    transaction_count: int
    applied_count: int
    imported_by_user_id: UUID4 | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ApplyAssignment(BaseModel):
    transaction_id: UUID4
    capital_call_item_id: UUID4
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise ValueError("amount must be greater than 0")
        return value


class ApplyImportRequest(BaseModel):
    assignments: list[ApplyAssignment] = Field(default_factory=list)
    ignore_transaction_ids: list[UUID4] = Field(default_factory=list)
