from datetime import datetime
from decimal import Decimal

from pydantic import UUID4, BaseModel, ConfigDict, Field


class InvestorCreate(BaseModel):
    organization_id: UUID4 | None = None
    investor_code: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    investor_type: str | None = Field(default=None, max_length=100)
    accredited: bool | None = False
    notes: str | None = None


class InvestorUpdate(BaseModel):
    investor_code: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    investor_type: str | None = Field(default=None, max_length=100)
    accredited: bool | None = None
    notes: str | None = None


class InvestorRead(BaseModel):
    id: UUID4
    organization_id: UUID4
    investor_code: str | None
    name: str
    investor_type: str | None
    accredited: bool | None
    notes: str | None
    total_committed: Decimal
    fund_count: int
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InvestorContactSummary(BaseModel):
    """The contact shown against an investor in the register."""

    id: UUID4
    first_name: str
    last_name: str
    email: str | None

    model_config = ConfigDict(from_attributes=True)


class InvestorListItem(BaseModel):
    id: UUID4
    organization_id: UUID4
    investor_code: str | None
    name: str
    investor_type: str | None
    accredited: bool | None
    total_committed: Decimal
    fund_count: int
    # The contact flagged is_primary, or None when the investor has no contacts
    # or none of them is flagged.
    primary_contact: InvestorContactSummary | None = None

    model_config = ConfigDict(from_attributes=True)
