"""Tests for the /dashboard/overview endpoint."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (CapitalCall, CapitalCallStatus, Commitment,
                        CommitmentStatus, Distribution, DistributionStatus,
                        Fund, FundStatus, Investor, Organization,
                        OrganizationType, User, UserRole)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_user():
    """Replace the auth dependency with a fake JWT payload, then clean up."""

    def _set(subject_id: str | None) -> None:
        app.dependency_overrides[get_current_user] = lambda: (
            {"sub": subject_id} if subject_id is not None else {}
        )

    yield _set
    app.dependency_overrides.clear()


def _create_org_user(subject_id: str = "hanko-1") -> tuple[int, int]:
    """Insert one Organization + linked User and return (org_id, user_id)."""
    db = SessionLocal()
    try:
        org = Organization(name="Eden Capital", type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.flush()
        user = User(
            organization_id=org.id,
            role=UserRole.fund_manager,
            first_name="Margot",
            last_name="Lane",
            email=f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.commit()
        return org.id, user.id
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
        assert Decimal(data["commitments_total_amount"]) == Decimal("0")
        assert data["capital_calls_outstanding"] == 0
        assert Decimal(data["distributions_ytd_amount"]) == Decimal("0")
        assert data["recent_funds"] == []
        assert data["upcoming_capital_calls"] == []

    def test_user_without_organization_returns_zeros(self, client, override_user):
        db = SessionLocal()
        try:
            user = User(
                organization_id=None,
                role=UserRole.lp,
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

    def test_aggregates_filtered_to_user_organization(self, client, override_user):
        org_id, _ = _create_org_user("hanko-1")
        # Foreign org — its data must not leak into the response
        other_org_id, _ = _create_org_user("hanko-other")

        db = SessionLocal()
        try:
            active_fund = Fund(
                organization_id=org_id,
                name="Eden Growth I",
                vintage_year=2024,
                strategy="Growth",
                currency_code="USD",
                status=FundStatus.active,
            )
            closed_fund = Fund(
                organization_id=org_id,
                name="Eden Legacy",
                vintage_year=2018,
                strategy="Buyout",
                currency_code="USD",
                status=FundStatus.closed,
            )
            other_fund = Fund(
                organization_id=other_org_id,
                name="Foreign Fund",
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
            db.add_all(
                [
                    Distribution(
                        fund_id=active_fund.id,
                        title="YTD distribution",
                        distribution_date=date(this_year, 3, 15),
                        amount=Decimal("75000.00"),
                        status=DistributionStatus.paid,
                    ),
                    Distribution(
                        fund_id=active_fund.id,
                        title="Last year distribution",
                        distribution_date=date(this_year - 1, 12, 1),
                        amount=Decimal("999999.00"),
                        status=DistributionStatus.paid,
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
        assert Decimal(data["commitments_total_amount"]) == Decimal("1000000.00")
        assert data["capital_calls_outstanding"] == 1
        assert Decimal(data["distributions_ytd_amount"]) == Decimal("75000.00")

        assert len(data["recent_funds"]) == 2
        fund_names = {f["name"] for f in data["recent_funds"]}
        assert fund_names == {"Eden Growth I", "Eden Legacy"}
        assert "Foreign Fund" not in fund_names

        active_summary = next(
            f for f in data["recent_funds"] if f["name"] == "Eden Growth I"
        )
        assert Decimal(active_summary["committed_amount"]) == Decimal("1000000.00")
        assert Decimal(active_summary["called_amount"]) == Decimal("250000.00")

        assert len(data["upcoming_capital_calls"]) == 1
        upcoming = data["upcoming_capital_calls"][0]
        assert upcoming["title"] == "Call 1"
        assert upcoming["fund_name"] == "Eden Growth I"
        assert upcoming["status"] == "scheduled"
