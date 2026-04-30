from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DistributionStatus, FundStatus


class DistributionFundSummary(BaseModel):
    id: int
    name: str
    currency_code: str
    status: FundStatus
    vintage_year: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DistributionItemCreate(BaseModel):
    commitment_id: int
    amount_due: Decimal
    note: str | None = None

    @field_validator("amount_due")
    @classmethod
    def _amount_due_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("amount_due must be greater than or equal to 0")
        return value


class DistributionItemUpdate(BaseModel):
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


class DistributionItemRead(BaseModel):
    id: int
    distribution_id: int
    commitment_id: int
    amount_due: Decimal
    amount_paid: Decimal
    paid_at: datetime | None
    note: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DistributionItemBulkCreate(BaseModel):
    items: list[DistributionItemCreate] = Field(default_factory=list)


class DistributionCreate(BaseModel):
    fund_id: int
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    distribution_date: date
    record_date: date | None = None
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise ValueError("amount must be greater than 0")
        return value


class DistributionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    distribution_date: date | None = None
    record_date: date | None = None
    amount: Decimal | None = None

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= Decimal("0"):
            raise ValueError("amount must be greater than 0")
        return value


class DistributionRead(BaseModel):
    id: int
    fund_id: int
    title: str
    description: str | None
    distribution_date: date
    record_date: date | None
    amount: Decimal
    status: DistributionStatus
    created_by_user_id: int | None
    created_at: datetime | None
    updated_at: datetime | None
    items: list[DistributionItemRead]
    fund: DistributionFundSummary

    model_config = ConfigDict(from_attributes=True)
