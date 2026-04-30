from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Query, Session

from app.core.database import get_db
from app.core.rbac import get_current_user_record
from app.models import (
    CapitalCall,
    CapitalCallStatus,
    Commitment,
    Distribution,
    DistributionItem,
    Fund,
    FundStatus,
    Investor,
    InvestorContact,
    Notification,
    NotificationStatus,
    Task,
    TaskStatus,
    User,
    UserRole,
)
from app.repositories.communication_repository import CommunicationRepository
from app.schemas import (
    CapitalCallSummary,
    CommunicationSummary,
    DashboardOverviewResponse,
    FundSummary,
)

router = APIRouter()

OUTSTANDING_CAPITAL_CALL_STATUSES = (
    CapitalCallStatus.scheduled,
    CapitalCallStatus.sent,
    CapitalCallStatus.partially_paid,
)


def _empty_response() -> DashboardOverviewResponse:
    return DashboardOverviewResponse(
        funds_active=0,
        investors_total=0,
        commitments_total_amount=Decimal("0"),
        capital_calls_outstanding=0,
        distributions_ytd_amount=Decimal("0"),
        unread_notifications_count=0,
        open_tasks_count=0,
        recent_funds=[],
        upcoming_capital_calls=[],
        recent_communications=[],
    )


def _visible_fund_ids(user: User) -> Select | None:
    """Subquery yielding fund ids the caller can see, or None for admin (no filter)."""
    if user.role is UserRole.admin:
        return None
    if user.role is UserRole.fund_manager:
        return select(Fund.id).where(Fund.organization_id == user.organization_id)
    return (
        select(Commitment.fund_id)
        .join(InvestorContact, InvestorContact.investor_id == Commitment.investor_id)
        .where(InvestorContact.user_id == user.id)
    )


def _visible_investor_ids(user: User) -> Select | None:
    """Subquery yielding investor ids the caller can see, or None for admin (no filter)."""
    if user.role is UserRole.admin:
        return None
    if user.role is UserRole.fund_manager:
        return select(Investor.id).where(
            Investor.organization_id == user.organization_id
        )
    return select(InvestorContact.investor_id).where(InvestorContact.user_id == user.id)


def _scope_by_fund(query: Query, fund_id_column, fund_filter: Select | None) -> Query:
    if fund_filter is None:
        return query
    return query.filter(fund_id_column.in_(fund_filter))


def _scope_by_investor(
    query: Query, investor_id_column, investor_filter: Select | None
) -> Query:
    if investor_filter is None:
        return query
    return query.filter(investor_id_column.in_(investor_filter))


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
) -> DashboardOverviewResponse:
    if (
        current_user.role is UserRole.fund_manager
        and current_user.organization_id is None
    ):
        return _empty_response()

    fund_filter = _visible_fund_ids(current_user)
    investor_filter = _visible_investor_ids(current_user)

    funds_active_q = db.query(func.count(Fund.id)).filter(
        Fund.status == FundStatus.active
    )
    funds_active = _scope_by_fund(funds_active_q, Fund.id, fund_filter).scalar() or 0

    investors_total_q = db.query(func.count(Investor.id))
    investors_total = (
        _scope_by_investor(investors_total_q, Investor.id, investor_filter).scalar()
        or 0
    )

    commitments_q = db.query(func.coalesce(func.sum(Commitment.committed_amount), 0))
    if current_user.role is UserRole.fund_manager:
        commitments_q = _scope_by_fund(commitments_q, Commitment.fund_id, fund_filter)
    else:
        commitments_q = _scope_by_investor(
            commitments_q, Commitment.investor_id, investor_filter
        )
    commitments_total_amount = commitments_q.scalar()

    capital_calls_q = db.query(func.count(CapitalCall.id)).filter(
        CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES)
    )
    capital_calls_outstanding = (
        _scope_by_fund(capital_calls_q, CapitalCall.fund_id, fund_filter).scalar() or 0
    )

    year_start = date(date.today().year, 1, 1)
    distributions_q = (
        db.query(func.coalesce(func.sum(DistributionItem.amount_paid), 0))
        .join(Distribution, Distribution.id == DistributionItem.distribution_id)
        .filter(DistributionItem.paid_at >= year_start)
    )
    distributions_ytd_amount = _scope_by_fund(
        distributions_q, Distribution.fund_id, fund_filter
    ).scalar()

    fund_agg_subq = (
        db.query(
            Commitment.fund_id.label("fund_id"),
            func.coalesce(func.sum(Commitment.committed_amount), 0).label(
                "committed_amount"
            ),
            func.coalesce(func.sum(Commitment.called_amount), 0).label("called_amount"),
        )
        .group_by(Commitment.fund_id)
        .subquery()
    )

    fund_rows_q = db.query(
        Fund,
        func.coalesce(fund_agg_subq.c.committed_amount, 0).label("committed_amount"),
        func.coalesce(fund_agg_subq.c.called_amount, 0).label("called_amount"),
    ).outerjoin(fund_agg_subq, fund_agg_subq.c.fund_id == Fund.id)
    fund_rows = (
        _scope_by_fund(fund_rows_q, Fund.id, fund_filter)
        .order_by(Fund.created_at.desc())
        .limit(5)
        .all()
    )

    recent_funds = [
        FundSummary(
            id=fund.id,
            name=fund.name,
            vintage_year=fund.vintage_year,
            strategy=fund.strategy,
            status=fund.status,
            currency_code=fund.currency_code,
            committed_amount=Decimal(str(committed)),
            called_amount=Decimal(str(called)),
            irr=None,
            tvpi=None,
        )
        for fund, committed, called in fund_rows
    ]

    upcoming_q = (
        db.query(CapitalCall, Fund.name)
        .join(Fund, Fund.id == CapitalCall.fund_id)
        .filter(CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES))
    )
    upcoming_rows = (
        _scope_by_fund(upcoming_q, Fund.id, fund_filter)
        .order_by(CapitalCall.due_date.asc())
        .limit(5)
        .all()
    )

    upcoming_capital_calls = [
        CapitalCallSummary(
            id=call.id,
            fund_id=call.fund_id,
            fund_name=fund_name,
            title=call.title,
            amount=call.amount,
            due_date=call.due_date,
            status=call.status,
        )
        for call, fund_name in upcoming_rows
    ]

    unread_notifications_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == current_user.id,
            Notification.status == NotificationStatus.unread,
        )
        .scalar()
        or 0
    )

    open_tasks_count = (
        db.query(func.count(Task.id))
        .filter(
            Task.assigned_to_user_id == current_user.id,
            Task.status.in_((TaskStatus.open, TaskStatus.in_progress)),
        )
        .scalar()
        or 0
    )

    communications = CommunicationRepository(db).list_recent_for_user(
        current_user, limit=5
    )
    recent_communications = [
        CommunicationSummary.model_validate(comm) for comm in communications
    ]

    return DashboardOverviewResponse(
        funds_active=funds_active,
        investors_total=investors_total,
        commitments_total_amount=Decimal(str(commitments_total_amount)),
        capital_calls_outstanding=capital_calls_outstanding,
        distributions_ytd_amount=Decimal(str(distributions_ytd_amount)),
        unread_notifications_count=unread_notifications_count,
        open_tasks_count=open_tasks_count,
        recent_funds=recent_funds,
        upcoming_capital_calls=upcoming_capital_calls,
        recent_communications=recent_communications,
    )
