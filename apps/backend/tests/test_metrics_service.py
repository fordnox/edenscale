"""Unit tests for the cashflow-derived fund metrics service."""

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.models import (
    CapitalCall,
    CapitalCallItem,
    CapitalCallStatus,
    Commitment,
    CommitmentStatus,
    Distribution,
    DistributionItem,
    DistributionStatus,
    Fund,
    Investor,
    Organization,
    OrganizationType,
)
from app.services.metrics import fund_cashflows, fund_metrics, xirr


class TestXirr:
    def test_known_one_year_double(self):
        # -100 then +200 one year later: IRR = 100%.
        flows = [
            (date(2025, 1, 1), Decimal("-100")),
            (date(2026, 1, 1), Decimal("200")),
        ]
        result = xirr(flows)
        assert result is not None
        assert abs(result - Decimal("1")) < Decimal("0.01")

    def test_known_one_year_ten_percent(self):
        flows = [
            (date(2025, 1, 1), Decimal("-1000")),
            (date(2026, 1, 1), Decimal("1100")),
        ]
        result = xirr(flows)
        assert result is not None
        assert abs(result - Decimal("0.1")) < Decimal("0.005")

    def test_multi_flow_schedule(self):
        # Two calls, one distribution; verify the result zeroes the NPV.
        flows = [
            (date(2025, 1, 1), Decimal("-500")),
            (date(2025, 7, 1), Decimal("-500")),
            (date(2026, 7, 1), Decimal("1200")),
        ]
        result = xirr(flows)
        assert result is not None
        rate = float(result)
        npv = sum(
            float(amount) / (1 + rate) ** ((d - date(2025, 1, 1)).days / 365)
            for d, amount in flows
        )
        assert abs(npv) < 1.0

    def test_empty_returns_none(self):
        assert xirr([]) is None

    def test_single_flow_returns_none(self):
        assert xirr([(date(2025, 1, 1), Decimal("-100"))]) is None

    def test_all_negative_returns_none(self):
        flows = [
            (date(2025, 1, 1), Decimal("-100")),
            (date(2026, 1, 1), Decimal("-100")),
        ]
        assert xirr(flows) is None

    def test_all_positive_returns_none(self):
        flows = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2026, 1, 1), Decimal("100")),
        ]
        assert xirr(flows) is None

    def test_zero_flows_ignored(self):
        flows = [
            (date(2025, 1, 1), Decimal("0")),
            (date(2026, 1, 1), Decimal("100")),
        ]
        assert xirr(flows) is None

    def test_same_day_flows_return_none(self):
        # No time elapsed: rate is undefined (constant NPV, no sign change
        # across the bracket).
        flows = [
            (date(2025, 1, 1), Decimal("-100")),
            (date(2025, 1, 1), Decimal("150")),
        ]
        assert xirr(flows) is None


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_fund_with_cashflows() -> str:
    db = SessionLocal()
    try:
        org = Organization(
            name="Metrics Org",
            slug=slugify("Metrics Org"),
            type=OrganizationType.fund_manager_firm,
        )
        db.add(org)
        db.flush()
        fund = Fund(organization_id=org.id, name="Fund M", slug="fund-m")
        db.add(fund)
        db.flush()
        investor = Investor(organization_id=org.id, name="LP M")
        db.add(investor)
        db.flush()
        commitment = Commitment(
            fund_id=fund.id,
            investor_id=investor.id,
            committed_amount=Decimal("1000.00"),
            called_amount=Decimal("400.00"),
            distributed_amount=Decimal("100.00"),
            commitment_date=date(2025, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(commitment)
        db.flush()
        call = CapitalCall(
            fund_id=fund.id,
            title="Call 1",
            due_date=date(2025, 2, 1),
            amount=Decimal("400.00"),
            status=CapitalCallStatus.paid,
        )
        db.add(call)
        db.flush()
        db.add(
            CapitalCallItem(
                capital_call_id=call.id,
                commitment_id=commitment.id,
                amount_due=Decimal("400.00"),
                amount_paid=Decimal("400.00"),
                paid_at=datetime(2025, 2, 1),
            )
        )
        distribution = Distribution(
            fund_id=fund.id,
            title="Dist 1",
            distribution_date=date(2026, 2, 1),
            amount=Decimal("100.00"),
            status=DistributionStatus.paid,
        )
        db.add(distribution)
        db.flush()
        db.add(
            DistributionItem(
                distribution_id=distribution.id,
                commitment_id=commitment.id,
                amount_due=Decimal("100.00"),
                amount_paid=Decimal("100.00"),
                paid_at=datetime(2026, 2, 1),
            )
        )
        db.commit()
        return str(fund.id)
    finally:
        db.close()


class TestFundMetrics:
    def test_aggregates_and_derived_ratios(self):
        fund_id = uuid.UUID(_seed_fund_with_cashflows())
        db = SessionLocal()
        try:
            metrics = fund_metrics(db, fund_id)
        finally:
            db.close()
        assert metrics.committed == Decimal("1000.00")
        assert metrics.called == Decimal("400.00")
        assert metrics.distributed == Decimal("100.00")
        assert metrics.dpi == Decimal("0.25")
        assert metrics.called_pct == Decimal("0.4")
        # -400 at 2025-02-01, +100 at 2026-02-01: deeply negative IRR.
        assert metrics.irr is not None
        assert metrics.irr < Decimal("0")

    def test_cashflows_ordering_and_signs(self):
        fund_id = uuid.UUID(_seed_fund_with_cashflows())
        db = SessionLocal()
        try:
            flows = fund_cashflows(db, fund_id)
        finally:
            db.close()
        assert flows == [
            (date(2025, 2, 1), Decimal("-400.00")),
            (date(2026, 2, 1), Decimal("100.00")),
        ]

    def test_empty_fund_returns_none_ratios(self):
        db = SessionLocal()
        try:
            org = Organization(
                name="Empty Org",
                slug="empty-org",
                type=OrganizationType.fund_manager_firm,
            )
            db.add(org)
            db.flush()
            fund = Fund(organization_id=org.id, name="Empty", slug="empty")
            db.add(fund)
            db.commit()
            metrics = fund_metrics(db, fund.id)
        finally:
            db.close()
        assert metrics.committed == Decimal("0")
        assert metrics.dpi is None
        assert metrics.called_pct is None
        assert metrics.irr is None
