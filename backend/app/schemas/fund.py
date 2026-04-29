from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FundStatus


class FundCreate(BaseModel):
    organization_id: int | None = None
    fund_group_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    vintage_year: int | None = None
    strategy: str | None = Field(default=None, max_length=255)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    target_size: Decimal | None = None
    hard_cap: Decimal | None = None
    status: FundStatus = FundStatus.draft
    inception_date: date | None = None
    close_date: date | None = None
    description: str | None = None


class FundUpdate(BaseModel):
    fund_group_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    vintage_year: int | None = None
    strategy: str | None = Field(default=None, max_length=255)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    target_size: Decimal | None = None
    hard_cap: Decimal | None = None
    status: FundStatus | None = None
    inception_date: date | None = None
    close_date: date | None = None
    description: str | None = None


class FundRead(BaseModel):
    id: int
    organization_id: int
    fund_group_id: int | None
    name: str
    legal_name: str | None
    vintage_year: int | None
    strategy: str | None
    currency_code: str
    target_size: Decimal | None
    hard_cap: Decimal | None
    current_size: Decimal
    status: FundStatus
    inception_date: date | None
    close_date: date | None
    description: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class FundListItem(BaseModel):
    id: int
    organization_id: int
    fund_group_id: int | None
    name: str
    currency_code: str
    target_size: Decimal | None
    current_size: Decimal
    status: FundStatus
    vintage_year: int | None

    model_config = ConfigDict(from_attributes=True)
