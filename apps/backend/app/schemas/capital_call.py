from datetime import date, datetime
from decimal import Decimal

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CapitalCallStatus, FundStatus


class CapitalCallFundSummary(BaseModel):
    id: UUID4
    name: str
    currency_code: str
    status: FundStatus
    vintage_year: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CapitalCallItemCreate(BaseModel):
    commitment_id: UUID4
    amount_due: Decimal
    note: str | None = None

    @field_validator("amount_due")
    @classmethod
    def _amount_due_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("amount_due must be greater than or equal to 0")
        return value


class CapitalCallItemUpdate(BaseModel):
    amount_due: Decimal | None = None
    amount_paid: Decimal | None = None
    paid_at: datetime | None = None
    note: str | None = None

    @field_validator("amount_due", "amount_paid")
    @classmethod
    def _amount_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < Decimal("0"):
            raise ValueError("amount must be greater than or equal to 0")
        return value


class CapitalCallItemRead(BaseModel):
    id: UUID4
    capital_call_id: UUID4
    commitment_id: UUID4
    amount_due: Decimal
    amount_paid: Decimal
    paid_at: datetime | None
    note: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class CapitalCallItemBulkCreate(BaseModel):
    items: list[CapitalCallItemCreate] = Field(default_factory=list)


class CapitalCallCreate(BaseModel):
    fund_id: UUID4
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    due_date: date
    call_date: date | None = None
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise ValueError("amount must be greater than 0")
        return value


class CapitalCallUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    due_date: date | None = None
    call_date: date | None = None
    amount: Decimal | None = None

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= Decimal("0"):
            raise ValueError("amount must be greater than 0")
        return value


class CapitalCallRead(BaseModel):
    id: UUID4
    fund_id: UUID4
    title: str
    description: str | None
    due_date: date
    call_date: date | None
    amount: Decimal
    status: CapitalCallStatus
    created_by_user_id: UUID4 | None
    created_at: datetime | None
    updated_at: datetime | None
    items: list[CapitalCallItemRead]
    fund: CapitalCallFundSummary

    model_config = ConfigDict(from_attributes=True)
