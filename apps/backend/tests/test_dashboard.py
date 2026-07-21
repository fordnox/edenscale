"""Tests for the /dashboard/overview endpoint."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import (
    CapitalCall,
    CapitalCallItem,
    CapitalCallStatus,
    Commitment,
    CommitmentStatus,
    Communication,
    CommunicationRecipient,
    CommunicationType,
    Distribution,
    DistributionItem,
    DistributionStatus,
    Fund,
    FundStatus,
    Investor,
    InvestorContact,
    Notification,
    NotificationStatus,
    Organization,
    OrganizationType,
    Task,
    TaskStatus,
    User,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _create_org_user(
    subject_id: str = "hanko-1",
    role: UserRole = UserRole.fund_manager,
    *,
    org_name: str = "NewTaven Capital",
) -> tuple[int, int]:
    """Insert one Organization + linked User + matching membership."""
    db = SessionLocal()
    try:
        org = Organization(
            name=org_name,
            slug=slugify(org_name),
            type=OrganizationType.fund_manager_firm,
        )
        db.add(org)
        db.flush()
        user = User(
            first_name="Margot",
            last_name="Lane",
            email=f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        db.add(
            UserOrganizationMembership(
                user_id=user.id,
                organization_id=org.id,
                role=role,
            )
        )
        db.commit()
        return org.id, user.id
    finally:
        db.close()


def _create_admin_user(subject_id: str, *, organization_ids: list[int]) -> int:
    """Create an admin user with one membership per org in ``organization_ids``."""
    db = SessionLocal()
    try:
        user = User(
            first_name="Root",
            last_name="Admin",
            email=f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        for org_id in organization_ids:
            db.add(
                UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=org_id,
                    role=UserRole.admin,
                )
            )
        db.commit()
        return user.id
    finally:
        db.close()


def _create_lp_user(subject_id: str, *, organization_id: int | None = None) -> int:
    db = SessionLocal()
    try:
        user = User(
            first_name="Lp",
            last_name="Holder",
            email=f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        if organization_id is not None:
            db.add(
                UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=organization_id,
                    role=UserRole.lp,
                )
            )
        db.commit()
        return user.id
    finally:
        db.close()


class TestDashboardOverview:
    def test_no_user_row_returns_zeros(self, client, override_user):
        override_user("nonexistent-subject")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["funds_active"] == 0
        assert data["investors_total"] == 0
        assert data["commitments_by_currency"] == []
        assert data["capital_calls_outstanding"] == 0
        assert data["distributions_ytd_by_currency"] == []
        assert data["unread_notifications_count"] == 0
        assert data["open_tasks_count"] == 0
        assert data["recent_funds"] == []
        assert data["upcoming_capital_calls"] == []
        assert data["recent_communications"] == []

    def test_user_without_organization_returns_zeros(self, client, override_user):
        db = SessionLocal()
        try:
            user = User(
                first_name="Solo",
                last_name="User",
                email="solo@example.com",
                hanko_subject_id="solo-1",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        override_user("solo-1")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["funds_active"] == 0
        assert data["recent_funds"] == []

    def test_financial_totals_are_grouped_by_fund_currency(self, client, override_user):
        org_id, _ = _create_org_user("hanko-currencies")
        db = SessionLocal()
        try:
            usd_fund = Fund(
                organization_id=org_id,
                name="Dollar Fund",
                slug="dollar-fund",
                currency_code="USD",
                status=FundStatus.active,
            )
            eur_fund = Fund(
                organization_id=org_id,
                name="Euro Fund",
                slug="euro-fund",
                currency_code="EUR",
                status=FundStatus.active,
            )
            investor = Investor(organization_id=org_id, name="Multi Currency LP")
            db.add_all([usd_fund, eur_fund, investor])
            db.flush()

            usd_commitment = Commitment(
                fund_id=usd_fund.id,
                investor_id=investor.id,
                committed_amount=Decimal("100.00"),
                commitment_date=date.today(),
                status=CommitmentStatus.approved,
            )
            eur_commitment = Commitment(
                fund_id=eur_fund.id,
                investor_id=investor.id,
                committed_amount=Decimal("200.00"),
                commitment_date=date.today(),
                status=CommitmentStatus.approved,
            )
            db.add_all([usd_commitment, eur_commitment])
            db.flush()

            usd_distribution = Distribution(
                fund_id=usd_fund.id,
                title="USD distribution",
                distribution_date=date.today(),
                amount=Decimal("10.00"),
                status=DistributionStatus.paid,
            )
            eur_distribution = Distribution(
                fund_id=eur_fund.id,
                title="EUR distribution",
                distribution_date=date.today(),
                amount=Decimal("20.00"),
                status=DistributionStatus.paid,
            )
            db.add_all([usd_distribution, eur_distribution])
            db.flush()
            db.add_all(
                [
                    DistributionItem(
                        distribution_id=usd_distribution.id,
                        commitment_id=usd_commitment.id,
                        amount_due=Decimal("10.00"),
                        amount_paid=Decimal("10.00"),
                        paid_at=datetime.now(timezone.utc),
                    ),
                    DistributionItem(
                        distribution_id=eur_distribution.id,
                        commitment_id=eur_commitment.id,
                        amount_due=Decimal("20.00"),
                        amount_paid=Decimal("20.00"),
                        paid_at=datetime.now(timezone.utc),
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-currencies")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["commitments_by_currency"] == [
            {"currency_code": "EUR", "amount": "200.00"},
            {"currency_code": "USD", "amount": "100.00"},
        ]
        assert data["distributions_ytd_by_currency"] == [
            {"currency_code": "EUR", "amount": "20.00"},
            {"currency_code": "USD", "amount": "10.00"},
        ]

    def test_aggregates_filtered_to_user_organization(self, client, override_user):
        org_id, _ = _create_org_user("hanko-1")
        # Foreign org — its data must not leak into the response
        other_org_id, _ = _create_org_user("hanko-other", org_name="Foreign Org")

        db = SessionLocal()
        try:
            active_fund = Fund(
                organization_id=org_id,
                name="NewTaven Growth I",
                slug=slugify("NewTaven Growth I"),
                vintage_year=2024,
                strategy="Growth",
                currency_code="USD",
                status=FundStatus.active,
            )
            closed_fund = Fund(
                organization_id=org_id,
                name="NewTaven Legacy",
                slug=slugify("NewTaven Legacy"),
                vintage_year=2018,
                strategy="Buyout",
                currency_code="USD",
                status=FundStatus.closed,
            )
            other_fund = Fund(
                organization_id=other_org_id,
                name="Foreign Fund",
                slug=slugify("Foreign Fund"),
                currency_code="USD",
                status=FundStatus.active,
            )
            db.add_all([active_fund, closed_fund, other_fund])
            db.flush()

            investor = Investor(organization_id=org_id, name="LP One")
            other_investor = Investor(organization_id=other_org_id, name="Foreign LP")
            db.add_all([investor, other_investor])
            db.flush()

            commitment = Commitment(
                fund_id=active_fund.id,
                investor_id=investor.id,
                committed_amount=Decimal("1000000.00"),
                called_amount=Decimal("250000.00"),
                commitment_date=date(2024, 1, 1),
                status=CommitmentStatus.approved,
            )
            db.add(commitment)
            db.flush()

            db.add_all(
                [
                    CapitalCall(
                        fund_id=active_fund.id,
                        title="Call 1",
                        due_date=date(2026, 6, 1),
                        amount=Decimal("100000.00"),
                        status=CapitalCallStatus.scheduled,
                    ),
                    CapitalCall(
                        fund_id=active_fund.id,
                        title="Call 2 (paid)",
                        due_date=date(2025, 1, 1),
                        amount=Decimal("50000.00"),
                        status=CapitalCallStatus.paid,
                    ),
                    # `overdue` DOES count toward outstanding: it is money that
                    # has been called but not received, and it is precisely the
                    # calls a daily cron flips into this status (from `sent`/
                    # `partially_paid`) that most need collection follow-up.
                    # `payment_matching` already treats `overdue` as collectible;
                    # the dashboard must not disagree and hide it.
                    CapitalCall(
                        fund_id=active_fund.id,
                        title="Call 3 (overdue)",
                        due_date=date(2025, 6, 1),
                        amount=Decimal("25000.00"),
                        status=CapitalCallStatus.overdue,
                    ),
                    CapitalCall(
                        fund_id=other_fund.id,
                        title="Foreign call",
                        due_date=date(2026, 5, 1),
                        amount=Decimal("999999.00"),
                        status=CapitalCallStatus.scheduled,
                    ),
                ]
            )

            this_year = date.today().year
            ytd_dist = Distribution(
                fund_id=active_fund.id,
                title="YTD distribution",
                distribution_date=date(this_year, 3, 15),
                amount=Decimal("75000.00"),
                status=DistributionStatus.paid,
            )
            last_year_dist = Distribution(
                fund_id=active_fund.id,
                title="Last year distribution",
                distribution_date=date(this_year - 1, 12, 1),
                amount=Decimal("999999.00"),
                status=DistributionStatus.paid,
            )
            db.add_all([ytd_dist, last_year_dist])
            db.flush()

            db.add_all(
                [
                    # Paid this year — must contribute to YTD total.
                    DistributionItem(
                        distribution_id=ytd_dist.id,
                        commitment_id=commitment.id,
                        amount_due=Decimal("75000.00"),
                        amount_paid=Decimal("75000.00"),
                        paid_at=datetime(this_year, 3, 20, 12, 0, 0),
                    ),
                    # Paid last year — must NOT contribute.
                    DistributionItem(
                        distribution_id=last_year_dist.id,
                        commitment_id=commitment.id,
                        amount_due=Decimal("999999.00"),
                        amount_paid=Decimal("999999.00"),
                        paid_at=datetime(this_year - 1, 12, 5, 12, 0, 0),
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-1")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        data = response.json()

        assert data["funds_active"] == 1
        assert data["investors_total"] == 1
        assert data["commitments_by_currency"] == [
            {"currency_code": "USD", "amount": "1000000.00"}
        ]
        # Call 1 (scheduled) + Call 3 (overdue) — overdue calls stay outstanding.
        assert data["capital_calls_outstanding"] == 2
        assert data["distributions_ytd_by_currency"] == [
            {"currency_code": "USD", "amount": "75000.00"}
        ]

        assert len(data["recent_funds"]) == 2
        fund_names = {f["name"] for f in data["recent_funds"]}
        assert fund_names == {"NewTaven Growth I", "NewTaven Legacy"}
        assert "Foreign Fund" not in fund_names

        active_summary = next(
            f for f in data["recent_funds"] if f["name"] == "NewTaven Growth I"
        )
        assert Decimal(active_summary["committed_amount"]) == Decimal("1000000.00")
        assert Decimal(active_summary["called_amount"]) == Decimal("250000.00")
        # Cashflow-derived summary metrics: DPI = distributed / called; TVPI
        # is gone (no NAV data exists to support it).
        assert "tvpi" not in active_summary
        assert active_summary["dpi"] is not None

        # Ordered by due_date ascending, so the overdue call (most urgent)
        # surfaces first, ahead of the merely-scheduled one.
        assert len(data["upcoming_capital_calls"]) == 2
        overdue_upcoming, scheduled_upcoming = data["upcoming_capital_calls"]
        assert overdue_upcoming["title"] == "Call 3 (overdue)"
        assert overdue_upcoming["fund_name"] == "NewTaven Growth I"
        assert overdue_upcoming["status"] == "overdue"
        assert scheduled_upcoming["title"] == "Call 1"
        assert scheduled_upcoming["fund_name"] == "NewTaven Growth I"
        assert scheduled_upcoming["status"] == "scheduled"

    def test_overdue_capital_call_counts_as_outstanding(self, client, override_user):
        """A past-due call flipped to `overdue` by the daily cron must stay
        visible — it is the money that most needs collection follow-up, and
        `payment_matching` already treats `overdue` as collectible."""
        org_id, _ = _create_org_user("hanko-overdue")
        db = SessionLocal()
        try:
            fund = Fund(
                organization_id=org_id,
                name="Overdue Fund",
                slug="overdue-fund",
                currency_code="USD",
                status=FundStatus.active,
            )
            db.add(fund)
            db.flush()

            db.add(
                CapitalCall(
                    fund_id=fund.id,
                    title="Past-due call",
                    due_date=date(2025, 1, 1),
                    amount=Decimal("10000.00"),
                    status=CapitalCallStatus.overdue,
                )
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-overdue")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        data = response.json()

        assert data["capital_calls_outstanding"] == 1
        assert len(data["upcoming_capital_calls"]) == 1
        assert data["upcoming_capital_calls"][0]["title"] == "Past-due call"
        assert data["upcoming_capital_calls"][0]["status"] == "overdue"

    def test_admin_with_multi_org_memberships_scopes_per_active_org(
        self, client, override_user
    ):
        """A multi-org admin sees only the org chosen via X-Organization-Id."""
        org_a, _ = _create_org_user("hanko-mgr-a", org_name="Org A")
        org_b, _ = _create_org_user("hanko-mgr-b", org_name="Org B")
        _create_admin_user("hanko-admin", organization_ids=[org_a, org_b])

        db = SessionLocal()
        try:
            fund_a = Fund(
                organization_id=org_a,
                name="Fund A",
                slug=slugify("Fund A"),
                currency_code="USD",
                status=FundStatus.active,
            )
            fund_b = Fund(
                organization_id=org_b,
                name="Fund B",
                slug=slugify("Fund B"),
                currency_code="USD",
                status=FundStatus.active,
            )
            db.add_all([fund_a, fund_b])
            db.flush()

            investor_a = Investor(organization_id=org_a, name="Investor A")
            investor_b = Investor(organization_id=org_b, name="Investor B")
            db.add_all([investor_a, investor_b])
            db.flush()

            db.add_all(
                [
                    Commitment(
                        fund_id=fund_a.id,
                        investor_id=investor_a.id,
                        committed_amount=Decimal("400000.00"),
                        commitment_date=date(2024, 1, 1),
                        status=CommitmentStatus.approved,
                    ),
                    Commitment(
                        fund_id=fund_b.id,
                        investor_id=investor_b.id,
                        committed_amount=Decimal("600000.00"),
                        commitment_date=date(2024, 2, 1),
                        status=CommitmentStatus.approved,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-admin")

        response_a = client.get(
            "/dashboard/overview", headers={"X-Organization-Id": str(org_a)}
        )
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert data_a["funds_active"] == 1
        assert {f["name"] for f in data_a["recent_funds"]} == {"Fund A"}
        assert data_a["commitments_by_currency"] == [
            {"currency_code": "USD", "amount": "400000.00"}
        ]

        response_b = client.get(
            "/dashboard/overview", headers={"X-Organization-Id": str(org_b)}
        )
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert data_b["funds_active"] == 1
        assert {f["name"] for f in data_b["recent_funds"]} == {"Fund B"}
        assert data_b["commitments_by_currency"] == [
            {"currency_code": "USD", "amount": "600000.00"}
        ]

    def test_lp_sees_only_their_commitments_and_investors(self, client, override_user):
        org_id, _ = _create_org_user("hanko-mgr")
        lp_user_id = _create_lp_user("hanko-lp", organization_id=org_id)

        db = SessionLocal()
        try:
            visible_fund = Fund(
                organization_id=org_id,
                name="Visible Fund",
                slug=slugify("Visible Fund"),
                currency_code="USD",
                status=FundStatus.active,
            )
            hidden_fund = Fund(
                organization_id=org_id,
                name="Hidden Fund",
                slug=slugify("Hidden Fund"),
                currency_code="USD",
                status=FundStatus.active,
            )
            db.add_all([visible_fund, hidden_fund])
            db.flush()

            visible_investor = Investor(organization_id=org_id, name="LP Investor")
            other_investor = Investor(organization_id=org_id, name="Other Investor")
            db.add_all([visible_investor, other_investor])
            db.flush()

            db.add(
                InvestorContact(
                    investor_id=visible_investor.id,
                    user_id=lp_user_id,
                    first_name="Lp",
                    last_name="Contact",
                )
            )

            visible_commitment = Commitment(
                fund_id=visible_fund.id,
                investor_id=visible_investor.id,
                committed_amount=Decimal("250000.00"),
                commitment_date=date(2024, 1, 1),
                status=CommitmentStatus.approved,
            )
            db.add(visible_commitment)
            db.add(
                Commitment(
                    fund_id=hidden_fund.id,
                    investor_id=other_investor.id,
                    committed_amount=Decimal("999999.00"),
                    commitment_date=date(2024, 2, 1),
                    status=CommitmentStatus.approved,
                )
            )
            db.flush()

            visible_call = CapitalCall(
                fund_id=visible_fund.id,
                title="Visible call",
                due_date=date(2026, 6, 1),
                amount=Decimal("50000.00"),
                status=CapitalCallStatus.scheduled,
            )
            db.add(visible_call)
            db.add(
                CapitalCall(
                    fund_id=hidden_fund.id,
                    title="Hidden call",
                    due_date=date(2026, 5, 1),
                    amount=Decimal("75000.00"),
                    status=CapitalCallStatus.scheduled,
                )
            )
            db.flush()
            # LP capital-call visibility is item-based (matching the
            # /capital-calls list endpoint): allocate the visible call to the
            # LP's commitment.
            db.add(
                CapitalCallItem(
                    capital_call_id=visible_call.id,
                    commitment_id=visible_commitment.id,
                    amount_due=Decimal("50000.00"),
                )
            )

            # Distributions YTD must be the LP's own receipts, not the
            # fund-wide total: pay the LP 10k and another investor 990k in
            # the same fund this year.
            other_commitment_same_fund = Commitment(
                fund_id=visible_fund.id,
                investor_id=other_investor.id,
                committed_amount=Decimal("500000.00"),
                commitment_date=date(2024, 3, 1),
                status=CommitmentStatus.approved,
            )
            db.add(other_commitment_same_fund)
            distribution = Distribution(
                fund_id=visible_fund.id,
                title="Shared distribution",
                distribution_date=date(date.today().year, 2, 1),
                amount=Decimal("1000000.00"),
                status=DistributionStatus.paid,
            )
            db.add(distribution)
            db.flush()
            db.add_all(
                [
                    DistributionItem(
                        distribution_id=distribution.id,
                        commitment_id=visible_commitment.id,
                        amount_due=Decimal("10000.00"),
                        amount_paid=Decimal("10000.00"),
                        paid_at=datetime(date.today().year, 2, 1),
                    ),
                    DistributionItem(
                        distribution_id=distribution.id,
                        commitment_id=other_commitment_same_fund.id,
                        amount_due=Decimal("990000.00"),
                        amount_paid=Decimal("990000.00"),
                        paid_at=datetime(date.today().year, 2, 1),
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-lp")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        data = response.json()

        assert data["funds_active"] == 1
        assert data["investors_total"] == 1
        assert data["commitments_by_currency"] == [
            {"currency_code": "USD", "amount": "250000.00"}
        ]
        assert data["capital_calls_outstanding"] == 1
        # Their own receipts only — not the fund-wide 1M.
        assert data["distributions_ytd_by_currency"] == [
            {"currency_code": "USD", "amount": "10000.00"}
        ]

        fund_names = {f["name"] for f in data["recent_funds"]}
        assert fund_names == {"Visible Fund"}

        upcoming_titles = {c["title"] for c in data["upcoming_capital_calls"]}
        assert upcoming_titles == {"Visible call"}


class TestDashboardActivityAggregates:
    def test_unread_notifications_count_only_for_current_user(
        self, client, override_user
    ):
        _, user_id = _create_org_user("hanko-1")
        _, other_user_id = _create_org_user("hanko-2", org_name="Other Org")

        db = SessionLocal()
        try:
            db.add_all(
                [
                    Notification(
                        user_id=user_id,
                        title="Hello",
                        message="Welcome",
                        status=NotificationStatus.unread,
                    ),
                    Notification(
                        user_id=user_id,
                        title="More",
                        message="Another",
                        status=NotificationStatus.unread,
                    ),
                    Notification(
                        user_id=user_id,
                        title="Stale",
                        message="Read already",
                        status=NotificationStatus.read,
                    ),
                    Notification(
                        user_id=user_id,
                        title="Filed",
                        message="Archived",
                        status=NotificationStatus.archived,
                    ),
                    # Another user — must not affect the count
                    Notification(
                        user_id=other_user_id,
                        title="Foreign",
                        message="Not mine",
                        status=NotificationStatus.unread,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-1")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        assert response.json()["unread_notifications_count"] == 2

    def test_open_tasks_count_only_counts_current_user_assignments(
        self, client, override_user
    ):
        org_id, user_id = _create_org_user("hanko-1")
        _, other_user_id = _create_org_user("hanko-2", org_name="Other Org")

        db = SessionLocal()
        try:
            fund = Fund(
                organization_id=org_id,
                name="NewTaven Fund",
                slug=slugify("NewTaven Fund"),
                currency_code="USD",
                status=FundStatus.active,
            )
            db.add(fund)
            db.flush()
            db.add_all(
                [
                    Task(
                        fund_id=fund.id,
                        assigned_to_user_id=user_id,
                        title="Open task",
                        status=TaskStatus.open,
                    ),
                    Task(
                        fund_id=fund.id,
                        assigned_to_user_id=user_id,
                        title="In progress",
                        status=TaskStatus.in_progress,
                    ),
                    Task(
                        fund_id=fund.id,
                        assigned_to_user_id=user_id,
                        title="Done",
                        status=TaskStatus.done,
                    ),
                    Task(
                        fund_id=fund.id,
                        assigned_to_user_id=user_id,
                        title="Cancelled",
                        status=TaskStatus.cancelled,
                    ),
                    # Foreign assignee — must not contribute
                    Task(
                        fund_id=fund.id,
                        assigned_to_user_id=other_user_id,
                        title="Foreign",
                        status=TaskStatus.open,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-1")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        assert response.json()["open_tasks_count"] == 2

    def test_recent_communications_only_sent_and_capped_to_five(
        self, client, override_user
    ):
        org_id, user_id = _create_org_user("hanko-1")

        db = SessionLocal()
        try:
            base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            for index in range(6):
                db.add(
                    Communication(
                        fund_id=None,
                        sender_user_id=user_id,
                        type=CommunicationType.announcement,
                        subject=f"Sent #{index}",
                        body="...",
                        sent_at=base + timedelta(days=index),
                    )
                )
            # Draft — must NOT appear in recent_communications
            db.add(
                Communication(
                    fund_id=None,
                    sender_user_id=user_id,
                    type=CommunicationType.announcement,
                    subject="Draft",
                    body="...",
                    sent_at=None,
                )
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-1")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        items = response.json()["recent_communications"]
        assert len(items) == 5
        subjects = [c["subject"] for c in items]
        assert subjects == ["Sent #5", "Sent #4", "Sent #3", "Sent #2", "Sent #1"]
        assert "Draft" not in subjects

    def test_recent_communications_filtered_by_lp_visibility(
        self, client, override_user
    ):
        org_id, fm_user_id = _create_org_user("hanko-mgr")
        lp_user_id = _create_lp_user("hanko-lp", organization_id=org_id)

        db = SessionLocal()
        try:
            fund = Fund(
                organization_id=org_id,
                name="Visible Fund",
                slug=slugify("Visible Fund"),
                currency_code="USD",
                status=FundStatus.active,
            )
            db.add(fund)
            db.flush()

            investor = Investor(organization_id=org_id, name="LP")
            db.add(investor)
            db.flush()

            contact = InvestorContact(
                investor_id=investor.id,
                user_id=lp_user_id,
                first_name="Lp",
                last_name="Contact",
            )
            db.add(contact)
            db.flush()

            visible = Communication(
                fund_id=fund.id,
                sender_user_id=fm_user_id,
                type=CommunicationType.announcement,
                subject="Visible to LP",
                body="...",
                sent_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
            )
            hidden = Communication(
                fund_id=fund.id,
                sender_user_id=fm_user_id,
                type=CommunicationType.announcement,
                subject="Hidden from LP",
                body="...",
                sent_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
            )
            db.add_all([visible, hidden])
            db.flush()

            db.add(
                CommunicationRecipient(
                    communication_id=visible.id,
                    user_id=lp_user_id,
                    investor_contact_id=contact.id,
                )
            )
            db.commit()
        finally:
            db.close()

        override_user("hanko-lp")
        response = client.get("/dashboard/overview")
        assert response.status_code == 200
        subjects = [c["subject"] for c in response.json()["recent_communications"]]
        assert subjects == ["Visible to LP"]
