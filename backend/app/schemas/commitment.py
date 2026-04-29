from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

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


class CommitmentUpdate(BaseModel):
    committed_amount: Decimal | None = None
    called_amount: Decimal | None = None
    distributed_amount: Decimal | None = None
    commitment_date: date | None = None
    share_class: str | None = Field(default=None, max_length=100)
    notes: str | None = None


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
