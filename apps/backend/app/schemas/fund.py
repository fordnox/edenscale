from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlparse

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import FundStatus


def _clean_website_url(value: str | None) -> str | None:
    """Normalise a fund's website to an absolute http(s) URL, or None.

    The value is rendered as an outbound link in the manager and LP apps, so
    schemes other than http/https (`javascript:`, `data:`) are rejected here
    rather than relying on every render site to sanitise it.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("website_url must be an absolute http:// or https:// URL")
    return cleaned


class FundCreate(BaseModel):
    organization_id: UUID4 | None = None
    fund_group_id: UUID4 | None = None
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
    website_url: str | None = Field(default=None, max_length=2048)

    _clean_website_url = field_validator("website_url")(_clean_website_url)


class FundUpdate(BaseModel):
    fund_group_id: UUID4 | None = None
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
    website_url: str | None = Field(default=None, max_length=2048)

    _clean_website_url = field_validator("website_url")(_clean_website_url)


class FundRead(BaseModel):
    id: UUID4
    organization_id: UUID4
    fund_group_id: UUID4 | None
    name: str
    slug: str
    legal_name: str | None
    vintage_year: int | None
    strategy: str | None
    currency_code: str
    target_size: Decimal | None
    hard_cap: Decimal | None
    current_size: Decimal
    # Latest fund-level net asset value (fair value), or None if never marked.
    nav: Decimal | None = None
    status: FundStatus
    inception_date: date | None
    close_date: date | None
    description: str | None
    website_url: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class FundListItem(BaseModel):
    id: UUID4
    organization_id: UUID4
    fund_group_id: UUID4 | None
    name: str
    slug: str
    currency_code: str
    target_size: Decimal | None
    current_size: Decimal
    nav: Decimal | None = None
    dpi: Decimal | None = None
    tvpi: Decimal | None = None
    irr: Decimal | None = None
    status: FundStatus
    vintage_year: int | None
    website_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FundOverview(BaseModel):
    fund_id: UUID4
    currency_code: str
    committed: Decimal
    called: Decimal
    distributed: Decimal
    remaining_commitment: Decimal
    # Fair-value metrics — populated once a fund valuation (NAV) has been marked.
    nav: Decimal | None = None
    irr: Decimal | None = None
    dpi: Decimal | None = None
    tvpi: Decimal | None = None
    rvpi: Decimal | None = None
    called_pct: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)
