"""Integration tests for the /investors and /investors/{id}/contacts routers."""

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


def _seed_investor(
    organization_id: int,
    *,
    name: str = "Acme LP",
    investor_code: str | None = None,
) -> int:
    db = SessionLocal()
    try:
        investor = Investor(
            organization_id=organization_id,
            name=name,
            investor_code=investor_code,
        )
        db.add(investor)
        db.commit()
        return investor.id
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


def _seed_commitment(
    fund_id: int,
    investor_id: int,
    *,
    committed_amount: Decimal = Decimal("250000.00"),
) -> int:
    db = SessionLocal()
    try:
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=committed_amount,
            commitment_date=date(2026, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(commitment)
        db.commit()
        return commitment.id
    finally:
        db.close()


def _seed_contact(
    investor_id: int,
    *,
    user_id: int | None = None,
    first_name: str = "Pat",
    last_name: str = "Lp",
    is_primary: bool = False,
) -> int:
    db = SessionLocal()
    try:
        contact = InvestorContact(
            investor_id=investor_id,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            is_primary=is_primary,
        )
        db.add(contact)
        db.commit()
        return contact.id
    finally:
        db.close()


class TestCreateInvestor:
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
            "/investors",
            json={"name": "Acme LP", "investor_code": "ACME-1"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme LP"
        assert data["investor_code"] == "ACME-1"
        assert data["organization_id"] == org_id
        assert Decimal(data["total_committed"]) == Decimal("0")
        assert data["fund_count"] == 0

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
            "/investors",
            json={"name": "Sneaky LP", "organization_id": other_org},
        )
        assert response.status_code == 201
        assert response.json()["organization_id"] == own_org

    def test_lp_cannot_create(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-lp", UserRole.lp, organization_id=org_id)
        override_user("hanko-lp")

        response = client.post("/investors", json={"name": "Forbidden LP"})
        assert response.status_code == 403


class TestInvestorWithContacts:
    def test_fund_manager_creates_investor_then_two_contacts(
        self, client, override_user
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        investor_response = client.post(
            "/investors",
            json={"name": "Acme LP"},
        )
        assert investor_response.status_code == 201
        investor_id = investor_response.json()["id"]

        first = client.post(
            f"/investors/{investor_id}/contacts",
            json={
                "first_name": "Alex",
                "last_name": "Primary",
                "is_primary": True,
            },
        )
        assert first.status_code == 201
        first_id = first.json()["id"]
        assert first.json()["is_primary"] is True

        second = client.post(
            f"/investors/{investor_id}/contacts",
            json={
                "first_name": "Sam",
                "last_name": "Secondary",
                "is_primary": False,
            },
        )
        assert second.status_code == 201
        assert second.json()["is_primary"] is False

        listing = client.get(f"/investors/{investor_id}/contacts")
        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 2
        primaries = {row["id"]: row["is_primary"] for row in rows}
        assert primaries[first_id] is True

    def test_setting_a_new_primary_clears_the_old_one(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        investor_id = _seed_investor(org_id)
        original_primary = _seed_contact(
            investor_id, first_name="Original", is_primary=True
        )
        secondary = _seed_contact(
            investor_id, first_name="Secondary", is_primary=False
        )

        response = client.patch(
            f"/investors/{investor_id}/contacts/{secondary}",
            json={"is_primary": True},
        )
        assert response.status_code == 200
        assert response.json()["is_primary"] is True

        listing = client.get(f"/investors/{investor_id}/contacts")
        assert listing.status_code == 200
        rows = {row["id"]: row["is_primary"] for row in listing.json()}
        assert rows[secondary] is True
        assert rows[original_primary] is False


class TestDeleteInvestor:
    def test_delete_with_commitments_returns_409(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        investor_id = _seed_investor(org_id)
        fund_id = _seed_fund(org_id)
        _seed_commitment(fund_id, investor_id)

        response = client.delete(f"/investors/{investor_id}")
        assert response.status_code == 409

    def test_delete_without_commitments_succeeds(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        investor_id = _seed_investor(org_id)

        response = client.delete(f"/investors/{investor_id}")
        assert response.status_code == 204

        get_response = client.get(f"/investors/{investor_id}")
        assert get_response.status_code == 404


class TestLpVisibility:
    def test_lp_only_sees_investors_they_are_a_contact_for(self, client, override_user):
        org_id = _seed_org()
        visible = _seed_investor(org_id, name="Visible LP")
        _seed_investor(org_id, name="Hidden LP")
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(visible, user_id=lp_user_id)

        override_user("hanko-lp")
        response = client.get("/investors")

        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["id"] == visible
        assert rows[0]["name"] == "Visible LP"
