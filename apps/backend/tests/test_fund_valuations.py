"""Fund valuation (NAV) metrics + endpoint tests.

NAV marks power the residual-value metrics: TVPI = (distributed + NAV) / called,
RVPI = NAV / called. Both are None until a fund is marked.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.core.slugs import slugify
from app.models import (
    Commitment,
    CommitmentStatus,
    Fund,
    FundValuation,
    Investor,
    Organization,
    OrganizationType,
    UserRole,
)
from app.services.metrics import fund_metrics, latest_fund_nav


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_fund_with_commitment(called: str, distributed: str, committed: str = "100000"):
    db = SessionLocal()
    try:
        org = Organization(
            name="NewTaven Capital",
            slug=slugify("NewTaven Capital"),
            type=OrganizationType.fund_manager_firm,
        )
        db.add(org)
        db.flush()
        fund = Fund(
            organization_id=org.id, name="Fund I", slug=slugify("Fund I"),
            currency_code="USD",
        )
        investor = Investor(organization_id=org.id, name="LP One")
        db.add_all([fund, investor])
        db.flush()
        db.add(
            Commitment(
                fund_id=fund.id,
                investor_id=investor.id,
                committed_amount=Decimal(committed),
                called_amount=Decimal(called),
                distributed_amount=Decimal(distributed),
                commitment_date=date(2026, 1, 1),
                status=CommitmentStatus.approved,
            )
        )
        db.commit()
        return fund.id
    finally:
        db.close()


class TestNavMetrics:
    def test_residual_metrics_none_without_valuation(self):
        fund_id = _seed_fund_with_commitment(called="60000", distributed="20000")
        db = SessionLocal()
        try:
            m = fund_metrics(db, fund_id)
            assert m.nav is None
            assert m.tvpi is None
            assert m.rvpi is None
            # DPI still works from cashflows.
            assert m.dpi == Decimal("0.3333")
        finally:
            db.close()

    def test_tvpi_rvpi_from_latest_nav(self):
        fund_id = _seed_fund_with_commitment(called="60000", distributed="20000")
        db = SessionLocal()
        try:
            db.add_all([
                FundValuation(
                    fund_id=fund_id, as_of_date=date(2026, 3, 31), nav=Decimal("50000")
                ),
                # A later mark supersedes the earlier one.
                FundValuation(
                    fund_id=fund_id, as_of_date=date(2026, 6, 30), nav=Decimal("70000")
                ),
            ])
            db.commit()

            assert latest_fund_nav(db, fund_id) == Decimal("70000")
            m = fund_metrics(db, fund_id)
            assert m.nav == Decimal("70000")
            # TVPI = (20000 + 70000) / 60000 = 1.5
            assert m.tvpi == Decimal("1.5000")
            # RVPI = 70000 / 60000 = 1.1667
            assert m.rvpi == Decimal("1.1667")
        finally:
            db.close()


class TestValuationEndpoints:
    def test_manager_creates_lp_reads_lp_cannot_write(
        self, client, override_user
    ):
        # Reuse the commitments-test seeding helpers via a fresh org/fund/LP.
        from tests.test_commitments_api import (
            _seed_commitment,
            _seed_contact,
            _seed_fund,
            _seed_investor,
            _seed_org,
            _seed_user,
        )

        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        lp_user_id = _seed_user(
            "hanko-lp", UserRole.lp, email="lp@example.com", organization_id=org_id
        )
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        _seed_contact(investor_id, lp_user_id)
        _seed_commitment(fund_id, investor_id)

        # Manager creates a valuation.
        override_user("hanko-fm")
        resp = client.post(
            f"/funds/{fund_id}/valuations",
            json={"as_of_date": "2026-03-31", "nav": "50000"},
        )
        assert resp.status_code == 201
        assert resp.json()["nav"] == "50000.00"

        # LP can read it.
        override_user("hanko-lp")
        listed = client.get(f"/funds/{fund_id}/valuations")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        # LP cannot create.
        forbidden = client.post(
            f"/funds/{fund_id}/valuations",
            json={"as_of_date": "2026-06-30", "nav": "60000"},
        )
        assert forbidden.status_code == 403
