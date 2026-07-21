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
    FundValuation,
    Investor,
    Organization,
    OrganizationType,
)
from app.services.metrics import (
    fund_cashflows,
    fund_metrics,
    fund_metrics_bulk,
    latest_fund_nav,
    latest_fund_navs,
    xirr,
)


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


# ---------------------------------------------------------------------------
# Step 4: fund_metrics_bulk / latest_fund_navs pinned against the single-fund
# versions. This equivalence test is what stops the bulk (funds-list) path
# from silently diverging from the single (fund-detail) path.
# ---------------------------------------------------------------------------


def _seed_fund_with_metrics(
    org_id: uuid.UUID,
    *,
    name: str,
    slug: str,
    committed: str,
    call_paid: str | None,
    call_paid_at: datetime | None,
    dist_paid: str | None,
    dist_paid_at: datetime | None,
    nav: str | None,
    nav_as_of: date | None = None,
) -> uuid.UUID:
    """Seed one fund with a commitment and, optionally, a paid capital-call
    item, a paid distribution item, and a NAV mark."""
    db = SessionLocal()
    try:
        fund = Fund(organization_id=org_id, name=name, slug=slug)
        db.add(fund)
        db.flush()
        investor = Investor(organization_id=org_id, name=f"LP {name}")
        db.add(investor)
        db.flush()
        commitment = Commitment(
            fund_id=fund.id,
            investor_id=investor.id,
            committed_amount=Decimal(committed),
            called_amount=Decimal(call_paid or "0"),
            distributed_amount=Decimal(dist_paid or "0"),
            commitment_date=date(2025, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(commitment)
        db.flush()

        if call_paid is not None:
            call = CapitalCall(
                fund_id=fund.id,
                title=f"Call {name}",
                due_date=date(2025, 2, 1),
                amount=Decimal(call_paid),
                status=CapitalCallStatus.paid,
            )
            db.add(call)
            db.flush()
            db.add(
                CapitalCallItem(
                    capital_call_id=call.id,
                    commitment_id=commitment.id,
                    amount_due=Decimal(call_paid),
                    amount_paid=Decimal(call_paid),
                    paid_at=call_paid_at,
                )
            )

        if dist_paid is not None:
            distribution = Distribution(
                fund_id=fund.id,
                title=f"Dist {name}",
                distribution_date=date(2026, 2, 1),
                amount=Decimal(dist_paid),
                status=DistributionStatus.paid,
            )
            db.add(distribution)
            db.flush()
            db.add(
                DistributionItem(
                    distribution_id=distribution.id,
                    commitment_id=commitment.id,
                    amount_due=Decimal(dist_paid),
                    amount_paid=Decimal(dist_paid),
                    paid_at=dist_paid_at,
                )
            )

        if nav is not None:
            db.add(
                FundValuation(
                    fund_id=fund.id,
                    as_of_date=nav_as_of or date(2026, 3, 1),
                    nav=Decimal(nav),
                )
            )

        db.commit()
        return fund.id
    finally:
        db.close()


class TestFundMetricsBulk:
    def _seed_three_funds(self, org_id: uuid.UUID) -> list[uuid.UUID]:
        fund_a = _seed_fund_with_metrics(
            org_id,
            name="Bulk A",
            slug="bulk-a",
            committed="1000.00",
            call_paid="400.00",
            call_paid_at=datetime(2025, 2, 1),
            dist_paid="100.00",
            dist_paid_at=datetime(2026, 2, 1),
            nav="500.00",
            nav_as_of=date(2026, 3, 1),
        )
        fund_b = _seed_fund_with_metrics(
            org_id,
            name="Bulk B",
            slug="bulk-b",
            committed="2000.00",
            call_paid="1500.00",
            call_paid_at=datetime(2025, 3, 1),
            dist_paid="300.00",
            dist_paid_at=datetime(2026, 4, 1),
            nav="1400.00",
            nav_as_of=date(2026, 5, 1),
        )
        fund_c = _seed_fund_with_metrics(
            org_id,
            name="Bulk C",
            slug="bulk-c",
            committed="500.00",
            call_paid=None,
            call_paid_at=None,
            dist_paid=None,
            dist_paid_at=None,
            nav=None,
        )
        return [fund_a, fund_b, fund_c]

    def test_bulk_matches_single_field_by_field(self):
        db = SessionLocal()
        try:
            org = Organization(
                name="Bulk Metrics Org",
                slug=slugify("Bulk Metrics Org"),
                type=OrganizationType.fund_manager_firm,
            )
            db.add(org)
            db.commit()
            org_id = org.id
        finally:
            db.close()

        fund_ids = self._seed_three_funds(org_id)

        db = SessionLocal()
        try:
            bulk = fund_metrics_bulk(db, fund_ids)
            for fund_id in fund_ids:
                single = fund_metrics(db, fund_id)
                bulk_metrics = bulk[fund_id]
                assert bulk_metrics.committed == single.committed, fund_id
                assert bulk_metrics.called == single.called, fund_id
                assert bulk_metrics.distributed == single.distributed, fund_id
                assert bulk_metrics.nav == single.nav, fund_id
                assert bulk_metrics.dpi == single.dpi, fund_id
                assert bulk_metrics.irr == single.irr, fund_id
                assert bulk_metrics.tvpi == single.tvpi, fund_id
                assert bulk_metrics.rvpi == single.rvpi, fund_id
                assert bulk_metrics.called_pct == single.called_pct, fund_id
            # Sanity: the marked fund actually has non-None residual metrics,
            # and the unmarked one doesn't — otherwise the equivalence above
            # would be vacuously true for the None fields.
            assert bulk[fund_ids[0]].nav == Decimal("500.00")
            assert bulk[fund_ids[0]].tvpi is not None
            assert bulk[fund_ids[2]].nav is None
            assert bulk[fund_ids[2]].tvpi is None
        finally:
            db.close()

    def test_empty_id_list_returns_empty_mapping(self):
        db = SessionLocal()
        try:
            assert fund_metrics_bulk(db, []) == {}
        finally:
            db.close()

    def test_unknown_fund_id_still_gets_an_entry(self):
        unknown_id = uuid.uuid4()
        db = SessionLocal()
        try:
            result = fund_metrics_bulk(db, [unknown_id])
        finally:
            db.close()
        assert unknown_id in result
        metrics = result[unknown_id]
        assert metrics.committed == Decimal("0")
        assert metrics.called == Decimal("0")
        assert metrics.distributed == Decimal("0")
        assert metrics.nav is None
        assert metrics.dpi is None
        assert metrics.tvpi is None
        assert metrics.rvpi is None
        assert metrics.irr is None
        assert metrics.called_pct is None

    def test_latest_fund_navs_matches_latest_fund_nav_per_fund(self):
        db = SessionLocal()
        try:
            org = Organization(
                name="NAV Bulk Org",
                slug=slugify("NAV Bulk Org"),
                type=OrganizationType.fund_manager_firm,
            )
            db.add(org)
            db.commit()
            org_id = org.id
        finally:
            db.close()

        fund_ids = self._seed_three_funds(org_id)

        db = SessionLocal()
        try:
            navs = latest_fund_navs(db, fund_ids)
            for fund_id in fund_ids:
                assert navs.get(fund_id) == latest_fund_nav(db, fund_id)
            # Fund C was never marked -> absent from the bulk map, matching
            # latest_fund_nav's None.
            assert fund_ids[2] not in navs
            assert latest_fund_nav(db, fund_ids[2]) is None
        finally:
            db.close()
