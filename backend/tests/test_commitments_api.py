"""Integration tests for the /commitments router and the nested
/funds/{id}/commitments and /investors/{id}/commitments routes."""

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
    Investor,
    InvestorContact,
    Organization,
    OrganizationType,
    User,
    UserRole,
)


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
        db.commit()
        return user.id
    finally:
        db.close()


def _seed_fund(organization_id: int, *, name: str = "Eden Fund I") -> int:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name)
        db.add(fund)
        db.commit()
        return fund.id
    finally:
        db.close()


def _seed_investor(organization_id: int, *, name: str = "Acme LP") -> int:
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name=name)
        db.add(investor)
        db.commit()
        return investor.id
    finally:
        db.close()


def _seed_commitment(
    fund_id: int,
    investor_id: int,
    *,
    committed_amount: Decimal = Decimal("250000.00"),
    status: CommitmentStatus = CommitmentStatus.pending,
) -> int:
    db = SessionLocal()
    try:
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=committed_amount,
            commitment_date=date(2026, 1, 1),
            status=status,
        )
        db.add(commitment)
        db.commit()
        return commitment.id
    finally:
        db.close()


def _seed_contact(investor_id: int, user_id: int) -> int:
    db = SessionLocal()
    try:
        contact = InvestorContact(
            investor_id=investor_id,
            user_id=user_id,
            first_name="Lp",
            last_name="Contact",
        )
        db.add(contact)
        db.commit()
        return contact.id
    finally:
        db.close()


class TestCreateCommitment:
    def test_fund_manager_creates_commitment(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)

        response = client.post(
            "/commitments",
            json={
                "fund_id": fund_id,
                "investor_id": investor_id,
                "committed_amount": "500000.00",
                "commitment_date": "2026-01-15",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["fund_id"] == fund_id
        assert data["investor_id"] == investor_id
        assert Decimal(data["committed_amount"]) == Decimal("500000.00")
        assert data["status"] == "pending"
        assert data["fund"]["id"] == fund_id
        assert data["investor"]["id"] == investor_id

    def test_duplicate_fund_investor_pair_returns_409(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        _seed_commitment(fund_id, investor_id)

        response = client.post(
            "/commitments",
            json={
                "fund_id": fund_id,
                "investor_id": investor_id,
                "committed_amount": "100000.00",
                "commitment_date": "2026-02-01",
            },
        )
        assert response.status_code == 409

    def test_called_amount_above_committed_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)

        response = client.post(
            "/commitments",
            json={
                "fund_id": fund_id,
                "investor_id": investor_id,
                "committed_amount": "100.00",
                "called_amount": "200.00",
                "commitment_date": "2026-01-15",
            },
        )
        assert response.status_code == 422


class TestStatusTransitions:
    def test_pending_to_approved(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        commitment_id = _seed_commitment(fund_id, investor_id)

        response = client.post(
            f"/commitments/{commitment_id}/status",
            json={"status": "approved"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    def test_terminal_declined_cannot_transition(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        commitment_id = _seed_commitment(
            fund_id, investor_id, status=CommitmentStatus.declined
        )

        response = client.post(
            f"/commitments/{commitment_id}/status",
            json={"status": "approved"},
        )
        assert response.status_code == 409

    def test_terminal_cancelled_cannot_transition(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        commitment_id = _seed_commitment(
            fund_id, investor_id, status=CommitmentStatus.cancelled
        )

        response = client.post(
            f"/commitments/{commitment_id}/status",
            json={"status": "pending"},
        )
        assert response.status_code == 409

    def test_approved_to_cancelled_allowed(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id)
        commitment_id = _seed_commitment(
            fund_id, investor_id, status=CommitmentStatus.approved
        )

        response = client.post(
            f"/commitments/{commitment_id}/status",
            json={"status": "cancelled"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"


class TestLpVisibility:
    def test_lp_lists_only_own_commitments_via_investor_route(
        self, client, override_user
    ):
        org_id = _seed_org()
        own_investor = _seed_investor(org_id, name="Own LP")
        other_investor = _seed_investor(org_id, name="Other LP")
        fund_id = _seed_fund(org_id)
        own_commitment = _seed_commitment(fund_id, own_investor)
        _seed_commitment(fund_id, other_investor)

        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(own_investor, lp_user_id)

        override_user("hanko-lp")
        response = client.get(f"/investors/{own_investor}/commitments")

        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["id"] == own_commitment

    def test_lp_listing_global_commitments_filters_to_own(
        self, client, override_user
    ):
        org_id = _seed_org()
        own_investor = _seed_investor(org_id, name="Own LP")
        other_investor = _seed_investor(org_id, name="Other LP")
        fund_id = _seed_fund(org_id)
        own_commitment = _seed_commitment(fund_id, own_investor)
        _seed_commitment(fund_id, other_investor)

        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(own_investor, lp_user_id)

        override_user("hanko-lp")
        response = client.get("/commitments")

        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert ids == [own_commitment]


class TestNestedFundRoute:
    def test_fund_manager_lists_commitments_under_fund(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_one = _seed_investor(org_id, name="LP One")
        investor_two = _seed_investor(org_id, name="LP Two")
        c_one = _seed_commitment(fund_id, investor_one)
        c_two = _seed_commitment(fund_id, investor_two)

        response = client.get(f"/funds/{fund_id}/commitments")
        assert response.status_code == 200
        ids = sorted(row["id"] for row in response.json())
        assert ids == sorted([c_one, c_two])
