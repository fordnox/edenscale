from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import CommitmentStatus, FundStatus


class CommitmentFundSummary(BaseModel):
    id: int
    name: str
    currency_code: str
    status: FundStatus
    vintage_year: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CommitmentInvestorSummary(BaseModel):
    id: int
    name: str
    investor_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CommitmentCreate(BaseModel):
    fund_id: int
    investor_id: int
    committed_amount: Decimal
    called_amount: Decimal = Decimal("0")
    # Why: distributed_amount is unbounded by committed_amount because private
    # funds can return more than was contributed (multiple-on-invested-capital
    # > 1 over the fund's life). Bounds belong to capital-call/distribution
    # items, not the commitment ledger row.
    distributed_amount: Decimal = Decimal("0")
    commitment_date: date
    status: CommitmentStatus = CommitmentStatus.pending
    share_class: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("committed_amount")
    @classmethod
    def _committed_amount_positive(cls, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise ValueError("committed_amount must be greater than 0")
        return value

    @field_validator("called_amount", "distributed_amount")
    @classmethod
    def _ledger_amount_non_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise ValueError("amount must be greater than or equal to 0")
        return value

    @model_validator(mode="after")
    def _called_within_committed(self) -> Self:
        if self.called_amount > self.committed_amount:
            raise ValueError("called_amount cannot exceed committed_amount")
        return self


class CommitmentUpdate(BaseModel):
    committed_amount: Decimal | None = None
    called_amount: Decimal | None = None
    distributed_amount: Decimal | None = None
    commitment_date: date | None = None
    share_class: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("committed_amount")
    @classmethod
    def _committed_amount_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= Decimal("0"):
            raise ValueError("committed_amount must be greater than 0")
        return value

    @field_validator("called_amount", "distributed_amount")
    @classmethod
    def _ledger_amount_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < Decimal("0"):
            raise ValueError("amount must be greater than or equal to 0")
        return value

    @model_validator(mode="after")
    def _called_within_committed(self) -> Self:
        # Only enforce the cross-field rule when both values are part of the
        # update payload; partial updates that touch only one side are
        # validated against the existing row in the repository layer if
        # tighter cross-row consistency becomes necessary.
        if (
            self.called_amount is not None
            and self.committed_amount is not None
            and self.called_amount > self.committed_amount
        ):
            raise ValueError("called_amount cannot exceed committed_amount")
        return self


class CommitmentStatusUpdate(BaseModel):
    status: CommitmentStatus


class CommitmentRead(BaseModel):
    id: int
    fund_id: int
    investor_id: int
    committed_amount: Decimal
    called_amount: Decimal
    distributed_amount: Decimal
    commitment_date: date
    status: CommitmentStatus
    share_class: str | None
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None
    fund: CommitmentFundSummary
    investor: CommitmentInvestorSummary

    model_config = ConfigDict(from_attributes=True)
