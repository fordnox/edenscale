from datetime import date, datetime
from decimal import Decimal

from pydantic import UUID4, BaseModel, ConfigDict, Field


class FundValuationCreate(BaseModel):
    as_of_date: date
    nav: Decimal = Field(ge=0)
    note: str | None = None


class FundValuationRead(BaseModel):
    id: UUID4
    fund_id: UUID4
    as_of_date: date
    nav: Decimal
    note: str | None
    created_by_user_id: UUID4 | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
