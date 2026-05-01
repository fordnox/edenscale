"""Integration tests for the /funds router."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Commitment,
    CommitmentStatus,
    Fund,
    FundStatus,
    Investor,
    InvestorContact,
    Organization,
    OrganizationType,
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


@pytest.fixture
def override_user():
    def _set(subject_id: str | None) -> None:
        app.dependency_overrides[get_current_user] = lambda: (
            {"sub": subject_id} if subject_id is not None else {}
        )

    yield _set
    app.dependency_overrides.clear()


def _seed_org(name: str = "Eden Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


def _seed_user(
    subject_id: str,
    role: UserRole,
    *,
    email: str | None = None,
    organization_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        user = User(
            organization_id=organization_id,
            role=role,
            first_name="First",
            last_name="Last",
            email=email or f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        if organization_id is not None:
            db.add(
                UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=organization_id,
                    role=role,
                )
            )
        db.commit()
        return user.id
    finally:
        db.close()


def _seed_fund(
    organization_id: int,
    *,
    name: str = "Eden Fund I",
    status: FundStatus = FundStatus.draft,
) -> int:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name, status=status)
        db.add(fund)
        db.commit()
        return fund.id
    finally:
        db.close()


def _seed_commitment_for_lp(
    fund_id: int,
    organization_id: int,
    user_id: int,
    *,
    committed_amount: Decimal = Decimal("100000.00"),
) -> None:
    """Create Investor + InvestorContact (linking the LP user) + Commitment."""
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name="LP Investor")
        db.add(investor)
        db.flush()
        contact = InvestorContact(
            investor_id=investor.id,
            user_id=user_id,
            first_name="Lp",
            last_name="Contact",
        )
        db.add(contact)
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor.id,
            committed_amount=committed_amount,
            commitment_date=date(2026, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(commitment)
        db.commit()
    finally:
        db.close()


class TestCreateFund:
    def test_fund_manager_creates_in_own_org(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.post(
            "/funds",
            json={"name": "Growth Fund I", "currency_code": "USD"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Growth Fund I"
        assert data["organization_id"] == org_id
        assert data["status"] == "draft"
        assert Decimal(data["current_size"]) == Decimal("0")

    def test_fund_manager_create_payload_org_is_overridden(self, client, override_user):
        own_org = _seed_org("Eden")
        other_org = _seed_org("Other")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=own_org,
        )
        override_user("hanko-fm")

        response = client.post(
            "/funds",
            json={"name": "Sneaky Fund", "organization_id": other_org},
        )
        assert response.status_code == 201
        assert response.json()["organization_id"] == own_org

    def test_lp_cannot_create(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        override_user("hanko-lp")

        response = client.post(
            "/funds",
            json={"name": "Forbidden Fund"},
        )
        assert response.status_code == 403


class TestListFunds:
    def test_lp_lists_only_funds_with_commitments(self, client, override_user):
        org_id = _seed_org()
        visible_fund_id = _seed_fund(org_id, name="Visible Fund")
        _seed_fund(org_id, name="Hidden Fund")

        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_commitment_for_lp(visible_fund_id, org_id, lp_user_id)

        override_user("hanko-lp")
        response = client.get("/funds")

        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["id"] == visible_fund_id
        assert rows[0]["name"] == "Visible Fund"
        assert Decimal(rows[0]["current_size"]) == Decimal("100000.00")

    def test_fund_manager_lists_own_org(self, client, override_user):
        own_org = _seed_org("Eden")
        other_org = _seed_org("Other")
        own_fund = _seed_fund(own_org, name="Eden Fund")
        _seed_fund(other_org, name="Other Fund")

        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=own_org,
        )
        override_user("hanko-fm")

        response = client.get("/funds")
        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert ids == [own_fund]


class TestCrossOrgScopingViaHeader:
    """A multi-org admin must use ``X-Organization-Id`` to pick which org to
    act through, and must only see / act on funds from that org. Asserts the
    Phase 02 contract that admin role is per-org, not global."""

    def _seed_multi_org_admin(self, subject_id: str, *, org_ids: list[int]) -> int:
        db = SessionLocal()
        try:
            user = User(
                organization_id=org_ids[0],
                role=UserRole.admin,
                first_name="Multi",
                last_name="Admin",
                email=f"{subject_id}@example.com",
                hanko_subject_id=subject_id,
            )
            db.add(user)
            db.flush()
            for org_id in org_ids:
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

    def test_multi_org_admin_must_pass_header(self, client, override_user):
        """No header + multi-org membership → 400 with the contract message."""
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        self._seed_multi_org_admin("hanko-multi", org_ids=[org_a, org_b])
        override_user("hanko-multi")

        response = client.get("/funds")
        assert response.status_code == 400
        assert "X-Organization-Id" in response.json()["detail"]

    def test_list_scopes_to_active_org_via_header(self, client, override_user):
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        fund_a = _seed_fund(org_a, name="Fund A")
        fund_b = _seed_fund(org_b, name="Fund B")
        self._seed_multi_org_admin("hanko-multi", org_ids=[org_a, org_b])
        override_user("hanko-multi")

        response_a = client.get("/funds", headers={"X-Organization-Id": str(org_a)})
        assert response_a.status_code == 200
        assert [r["id"] for r in response_a.json()] == [fund_a]

        response_b = client.get("/funds", headers={"X-Organization-Id": str(org_b)})
        assert response_b.status_code == 200
        assert [r["id"] for r in response_b.json()] == [fund_b]

    def test_get_fund_blocks_cross_org_leakage(self, client, override_user):
        """Fund detail must 403 when the active membership is for a
        different org than the fund (no fall-through to other-org rows)."""
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        fund_b = _seed_fund(org_b, name="Fund B")
        self._seed_multi_org_admin("hanko-multi", org_ids=[org_a, org_b])
        override_user("hanko-multi")

        response = client.get(
            f"/funds/{fund_b}", headers={"X-Organization-Id": str(org_a)}
        )
        assert response.status_code == 403

    def test_header_for_org_user_is_not_a_member_of_returns_403(
        self, client, override_user
    ):
        """Single-org admin spoofing a different org via the header gets
        403 from the dep — never reaches the router body."""
        own_org = _seed_org("Own")
        other_org = _seed_org("Other")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=own_org,
        )
        override_user("hanko-fm")

        response = client.get(
            "/funds", headers={"X-Organization-Id": str(other_org)}
        )
        assert response.status_code == 403


class TestArchiveFund:
    def test_archive_flips_status(self, client, override_user):
        org_id = _seed_org()
        fund_id = _seed_fund(org_id, status=FundStatus.active)
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.post(f"/funds/{fund_id}/archive")
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

        get_response = client.get(f"/funds/{fund_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "archived"


class TestFundOverview:
    def test_returns_fund_kpis(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id, status=FundStatus.active)

        db = SessionLocal()
        try:
            inv_a = Investor(organization_id=org_id, name="LP A")
            inv_b = Investor(organization_id=org_id, name="LP B")
            db.add_all([inv_a, inv_b])
            db.flush()
            db.add_all(
                [
                    Commitment(
                        fund_id=fund_id,
                        investor_id=inv_a.id,
                        committed_amount=Decimal("750000.00"),
                        called_amount=Decimal("300000.00"),
                        distributed_amount=Decimal("100000.00"),
                        commitment_date=date(2026, 1, 1),
                        status=CommitmentStatus.approved,
                    ),
                    Commitment(
                        fund_id=fund_id,
                        investor_id=inv_b.id,
                        committed_amount=Decimal("250000.00"),
                        called_amount=Decimal("50000.00"),
                        distributed_amount=Decimal("0.00"),
                        commitment_date=date(2026, 1, 5),
                        status=CommitmentStatus.approved,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        response = client.get(f"/funds/{fund_id}/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["fund_id"] == fund_id
        assert data["currency_code"] == "USD"
        assert Decimal(data["committed"]) == Decimal("1000000.00")
        assert Decimal(data["called"]) == Decimal("350000.00")
        assert Decimal(data["distributed"]) == Decimal("100000.00")
        assert Decimal(data["remaining_commitment"]) == Decimal("650000.00")
        assert data["irr"] is None

    def test_zero_commitments_returns_zeros(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        response = client.get(f"/funds/{fund_id}/overview")
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["committed"]) == Decimal("0")
        assert Decimal(data["called"]) == Decimal("0")
        assert Decimal(data["distributed"]) == Decimal("0")
        assert Decimal(data["remaining_commitment"]) == Decimal("0")

    def test_unknown_fund_returns_404(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.get("/funds/9999/overview")
        assert response.status_code == 404

    def test_fund_manager_cannot_view_other_org_overview(self, client, override_user):
        own_org = _seed_org("Own")
        other_org = _seed_org("Other")
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=own_org,
        )
        override_user("hanko-fm")
        other_fund = _seed_fund(other_org, name="Other Fund")

        response = client.get(f"/funds/{other_fund}/overview")
        assert response.status_code == 403

    def test_lp_can_view_overview_for_their_fund(self, client, override_user):
        org_id = _seed_org()
        fund_id = _seed_fund(org_id, status=FundStatus.active)
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_commitment_for_lp(
            fund_id,
            org_id,
            lp_user_id,
            committed_amount=Decimal("500000.00"),
        )
        override_user("hanko-lp")

        response = client.get(f"/funds/{fund_id}/overview")
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["committed"]) == Decimal("500000.00")
