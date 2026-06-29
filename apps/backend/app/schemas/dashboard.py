from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import CapitalCallStatus, CommunicationType, FundStatus


class FundSummary(BaseModel):
    id: int
    name: str
    vintage_year: int | None = None
    strategy: str | None = None
    status: FundStatus
    currency_code: str
    committed_amount: Decimal
    called_amount: Decimal
    irr: Decimal | None = None
    tvpi: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class CapitalCallSummary(BaseModel):
    id: int
    fund_id: int
    fund_name: str
    title: str
    amount: Decimal
    due_date: date
    status: CapitalCallStatus

    model_config = ConfigDict(from_attributes=True)


class CommunicationSummary(BaseModel):
    id: int
    fund_id: int | None
    sender_user_id: int | None
    type: CommunicationType
    subject: str
    sent_at: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DashboardOverviewResponse(BaseModel):
    funds_active: int
    investors_total: int
    commitments_total_amount: Decimal
    capital_calls_outstanding: int
    distributions_ytd_amount: Decimal
    unread_notifications_count: int
    open_tasks_count: int
    recent_funds: list[FundSummary]
    upcoming_capital_calls: list[CapitalCallSummary]
    recent_communications: list[CommunicationSummary]

    model_config = ConfigDict(from_attributes=True)
