"""Fund performance metrics derived from recorded cashflows.

All figures come from capital-call / distribution items — there is no NAV
or valuation mark in the data model, so residual-value metrics (TVPI, RVPI)
are intentionally absent. ``called_amount`` on commitments is the sum of
*paid* capital-call items, so "called" throughout equals paid-in capital.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.distribution import Distribution
from app.models.distribution_item import DistributionItem

_QUANT = Decimal("0.0001")
_MAX_ITERATIONS = 100
_TOLERANCE = 1e-9
_RATE_LOWER = -0.999
_RATE_UPPER = 10.0


@dataclass(frozen=True)
class FundMetrics:
    committed: Decimal
    called: Decimal  # paid-in capital (sum of paid capital-call items)
    distributed: Decimal
    dpi: Decimal | None
    irr: Decimal | None
    called_pct: Decimal | None


def _npv(rate: float, flows: list[tuple[float, float]]) -> float:
    return sum(amount / (1.0 + rate) ** years for years, amount in flows)


def xirr(cashflows: list[tuple[date, Decimal]]) -> Decimal | None:
    """Annualized IRR of dated cashflows (negative = paid in, positive = received).

    Returns None when the rate is undefined: fewer than two flows, all flows
    on one side, or no convergence within the bracketing bounds.
    """
    flows = [(d, float(a)) for d, a in cashflows if a != 0]
    if len(flows) < 2:
        return None
    if all(a > 0 for _, a in flows) or all(a < 0 for _, a in flows):
        return None
    t0 = min(d for d, _ in flows)
    scaled = [((d - t0).days / 365.0, a) for d, a in flows]

    lo, hi = _RATE_LOWER, _RATE_UPPER
    npv_lo, npv_hi = _npv(lo, scaled), _npv(hi, scaled)
    if npv_lo * npv_hi > 0:
        return None

    rate = 0.1
    for _ in range(_MAX_ITERATIONS):
        npv = _npv(rate, scaled)
        if abs(npv) < _TOLERANCE:
            break
        derivative = sum(
            -years * amount / (1.0 + rate) ** (years + 1.0)
            for years, amount in scaled
            if years > 0
        )
        next_rate = rate - npv / derivative if derivative else None
        if next_rate is None or not (lo < next_rate < hi):
            # Newton step escaped the bracket; fall back to bisection.
            if _npv(lo, scaled) * npv < 0:
                hi = rate
            else:
                lo = rate
            next_rate = (lo + hi) / 2.0
        if abs(next_rate - rate) < _TOLERANCE:
            rate = next_rate
            break
        rate = next_rate
    else:
        if abs(_npv(rate, scaled)) > 1e-4:
            return None
    return Decimal(str(rate)).quantize(_QUANT)


def _flow_date(paid_at: datetime | date) -> date:
    return paid_at.date() if isinstance(paid_at, datetime) else paid_at


def fund_cashflows(db: Session, fund_id: uuid.UUID) -> list[tuple[date, Decimal]]:
    """Dated net cashflows for a fund from the LP perspective:
    paid capital-call items are outflows, paid distribution items inflows."""
    call_rows = (
        db.query(CapitalCallItem.paid_at, CapitalCallItem.amount_paid)
        .join(CapitalCall, CapitalCall.id == CapitalCallItem.capital_call_id)
        .filter(
            CapitalCall.fund_id == fund_id,
            CapitalCallItem.paid_at.is_not(None),
            CapitalCallItem.amount_paid > 0,
        )
        .all()
    )
    dist_rows = (
        db.query(DistributionItem.paid_at, DistributionItem.amount_paid)
        .join(Distribution, Distribution.id == DistributionItem.distribution_id)
        .filter(
            Distribution.fund_id == fund_id,
            DistributionItem.paid_at.is_not(None),
            DistributionItem.amount_paid > 0,
        )
        .all()
    )
    flows = [
        (_flow_date(paid_at), -Decimal(str(amount))) for paid_at, amount in call_rows
    ]
    flows += [
        (_flow_date(paid_at), Decimal(str(amount))) for paid_at, amount in dist_rows
    ]
    flows.sort(key=lambda f: f[0])
    return flows


def fund_metrics(db: Session, fund_id: uuid.UUID) -> FundMetrics:
    committed, called, distributed = (
        Decimal(str(value or 0))
        for value in db.query(
            func.coalesce(func.sum(Commitment.committed_amount), 0),
            func.coalesce(func.sum(Commitment.called_amount), 0),
            func.coalesce(func.sum(Commitment.distributed_amount), 0),
        )
        .filter(Commitment.fund_id == fund_id)
        .one()
    )
    dpi = (distributed / called).quantize(_QUANT) if called > 0 else None
    called_pct = (called / committed).quantize(_QUANT) if committed > 0 else None
    irr = xirr(fund_cashflows(db, fund_id))
    return FundMetrics(
        committed=committed,
        called=called,
        distributed=distributed,
        dpi=dpi,
        irr=irr,
        called_pct=called_pct,
    )
