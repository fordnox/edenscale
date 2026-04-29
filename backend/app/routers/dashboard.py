from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import (
    CapitalCall,
    CapitalCallStatus,
    Commitment,
    Distribution,
    Fund,
    FundStatus,
    Investor,
    User,
)
from app.schemas import CapitalCallSummary, DashboardOverviewResponse, FundSummary

router = APIRouter()

OUTSTANDING_CAPITAL_CALL_STATUSES = (
    CapitalCallStatus.scheduled,
    CapitalCallStatus.sent,
    CapitalCallStatus.partially_paid,
    CapitalCallStatus.overdue,
)


def _empty_response() -> DashboardOverviewResponse:
    return DashboardOverviewResponse(
        funds_active=0,
        investors_total=0,
        commitments_total_amount=Decimal("0"),
        capital_calls_outstanding=0,
        distributions_ytd_amount=Decimal("0"),
        recent_funds=[],
        upcoming_capital_calls=[],
    )


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_overview(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> DashboardOverviewResponse:
    subject_id = current_user.get("sub")
    if not subject_id:
        return _empty_response()

    user = db.query(User).filter(User.hanko_subject_id == subject_id).first()
    if user is None or user.organization_id is None:
        return _empty_response()

    org_id = user.organization_id

    funds_active = (
        db.query(func.count(Fund.id))
        .filter(Fund.organization_id == org_id, Fund.status == FundStatus.active)
        .scalar()
        or 0
    )

    investors_total = (
        db.query(func.count(Investor.id))
        .filter(Investor.organization_id == org_id)
        .scalar()
        or 0
    )

    commitments_total_amount = (
        db.query(func.coalesce(func.sum(Commitment.committed_amount), 0))
        .join(Fund, Fund.id == Commitment.fund_id)
        .filter(Fund.organization_id == org_id)
        .scalar()
    )

    capital_calls_outstanding = (
        db.query(func.count(CapitalCall.id))
        .join(Fund, Fund.id == CapitalCall.fund_id)
        .filter(
            Fund.organization_id == org_id,
            CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES),
        )
        .scalar()
        or 0
    )

    year_start = date(date.today().year, 1, 1)
    distributions_ytd_amount = (
        db.query(func.coalesce(func.sum(Distribution.amount), 0))
        .join(Fund, Fund.id == Distribution.fund_id)
        .filter(
            Fund.organization_id == org_id,
            Distribution.distribution_date >= year_start,
        )
        .scalar()
    )

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

    fund_rows = (
        db.query(
            Fund,
            func.coalesce(fund_agg_subq.c.committed_amount, 0).label(
                "committed_amount"
            ),
            func.coalesce(fund_agg_subq.c.called_amount, 0).label("called_amount"),
        )
        .outerjoin(fund_agg_subq, fund_agg_subq.c.fund_id == Fund.id)
        .filter(Fund.organization_id == org_id)
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

    upcoming_rows = (
        db.query(CapitalCall, Fund.name)
        .join(Fund, Fund.id == CapitalCall.fund_id)
        .filter(
            Fund.organization_id == org_id,
            CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES),
        )
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

    return DashboardOverviewResponse(
        funds_active=funds_active,
        investors_total=investors_total,
        commitments_total_amount=Decimal(str(commitments_total_amount)),
        capital_calls_outstanding=capital_calls_outstanding,
        distributions_ytd_amount=Decimal(str(distributions_ytd_amount)),
        recent_funds=recent_funds,
        upcoming_capital_calls=upcoming_capital_calls,
    )
