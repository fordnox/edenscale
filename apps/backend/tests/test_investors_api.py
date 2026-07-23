"""Integration tests for the /investors and /investors/{id}/contacts routers."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
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
from app.models.user_organization_membership import UserOrganizationMembership


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_org(name: str = "NewTaven Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(
            name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm
        )
        db.add(org)
        db.commit()
        return str(org.id)
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
        return str(user.id)
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
        return str(investor.id)
    finally:
        db.close()


def _seed_fund(organization_id: int, *, name: str = "NewTaven Fund I") -> int:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name, slug=slugify(name))
        db.add(fund)
        db.commit()
        return str(fund.id)
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
        return str(commitment.id)
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
        return str(contact.id)
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
        own_org = _seed_org("NewTaven")
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
        secondary = _seed_contact(investor_id, first_name="Secondary", is_primary=False)

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


class TestInvestorType:
    def _as_fund_manager(self, override_user, org_id):
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

    def test_accepts_an_enum_member(self, client, override_user):
        org_id = _seed_org()
        self._as_fund_manager(override_user, org_id)

        response = client.post(
            "/investors",
            json={"name": "Beacon", "investor_type": "family_office"},
        )
        assert response.status_code == 201
        assert response.json()["investor_type"] == "family_office"

    @pytest.mark.parametrize(
        "value", ["Family Office", "family office", "hedge_fund", "", "  "]
    )
    def test_writes_reject_anything_outside_the_enum(
        self, client, override_user, value
    ):
        org_id = _seed_org()
        self._as_fund_manager(override_user, org_id)

        response = client.post(
            "/investors", json={"name": "Beacon", "investor_type": value}
        )
        assert response.status_code == 422

    def test_null_is_allowed_and_round_trips(self, client, override_user):
        org_id = _seed_org()
        self._as_fund_manager(override_user, org_id)

        created = client.post("/investors", json={"name": "Untyped"})
        assert created.status_code == 201
        assert created.json()["investor_type"] is None

    def test_patch_changes_and_clears_the_type(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        self._as_fund_manager(override_user, org_id)

        changed = client.patch(
            f"/investors/{investor_id}", json={"investor_type": "pension"}
        )
        assert changed.status_code == 200
        assert changed.json()["investor_type"] == "pension"

        cleared = client.patch(
            f"/investors/{investor_id}", json={"investor_type": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["investor_type"] is None

    def test_reads_tolerate_legacy_free_text(self, client, override_user):
        """Rows written before the enum existed must still be readable.

        The column is plain text, so the response models stay permissive; only
        writes are constrained.
        """
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        db = SessionLocal()
        try:
            row = db.query(Investor).filter(Investor.id == investor_id).one()
            row.investor_type = "Hedge Fund"
            db.commit()
        finally:
            db.close()
        self._as_fund_manager(override_user, org_id)

        assert (
            client.get(f"/investors/{investor_id}").json()["investor_type"]
            == "Hedge Fund"
        )
        rows = client.get("/investors").json()
        assert (
            next(r for r in rows if r["id"] == investor_id)["investor_type"]
            == "Hedge Fund"
        )

    def test_type_appears_in_the_list(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        self._as_fund_manager(override_user, org_id)
        client.patch(f"/investors/{investor_id}", json={"investor_type": "endowment"})

        rows = client.get("/investors").json()
        row = next(r for r in rows if r["id"] == investor_id)
        assert row["investor_type"] == "endowment"


class TestListPrimaryContact:
    """The register shows each investor's primary contact, or nothing."""

    def _as_fund_manager(self, override_user, org_id):
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

    def _row(self, client, investor_id):
        response = client.get("/investors")
        assert response.status_code == 200
        return next(r for r in response.json() if r["id"] == investor_id)

    def test_returns_the_primary_contact(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        _seed_contact(investor_id, first_name="Ada", last_name="Byron", is_primary=True)
        self._as_fund_manager(override_user, org_id)

        contact = self._row(client, investor_id)["primary_contact"]
        assert contact is not None
        assert (contact["first_name"], contact["last_name"]) == ("Ada", "Byron")

    def test_none_when_investor_has_no_contacts(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        self._as_fund_manager(override_user, org_id)

        assert self._row(client, investor_id)["primary_contact"] is None

    def test_none_when_no_contact_is_flagged_primary(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        _seed_contact(investor_id, first_name="Grace", is_primary=False)
        _seed_contact(investor_id, first_name="Alan", is_primary=False)
        self._as_fund_manager(override_user, org_id)

        assert self._row(client, investor_id)["primary_contact"] is None

    def test_picks_only_the_flagged_contact(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        _seed_contact(investor_id, first_name="Grace", is_primary=False)
        _seed_contact(investor_id, first_name="Alan", is_primary=True)
        self._as_fund_manager(override_user, org_id)

        assert self._row(client, investor_id)["primary_contact"]["first_name"] == "Alan"

    def test_contacts_do_not_leak_across_investors(self, client, override_user):
        org_id = _seed_org()
        with_contact = _seed_investor(org_id, name="Has Contact")
        without = _seed_investor(org_id, name="No Contact")
        _seed_contact(with_contact, first_name="Ada", is_primary=True)
        self._as_fund_manager(override_user, org_id)

        assert self._row(client, with_contact)["primary_contact"] is not None
        assert self._row(client, without)["primary_contact"] is None


class TestDeleteContact:
    def _as_fund_manager(self, override_user, org_id):
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

    def test_deletes_a_non_primary_contact(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        _seed_contact(investor_id, first_name="Ada", is_primary=True)
        secondary = _seed_contact(investor_id, first_name="Sam", is_primary=False)
        self._as_fund_manager(override_user, org_id)

        response = client.delete(f"/investors/{investor_id}/contacts/{secondary}")
        assert response.status_code == 200

        remaining = client.get(f"/investors/{investor_id}/contacts").json()
        assert [c["first_name"] for c in remaining] == ["Ada"]

    def test_refuses_to_delete_the_primary_contact(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        primary = _seed_contact(investor_id, first_name="Ada", is_primary=True)
        _seed_contact(investor_id, first_name="Sam", is_primary=False)
        self._as_fund_manager(override_user, org_id)

        response = client.delete(f"/investors/{investor_id}/contacts/{primary}")
        assert response.status_code == 409

        remaining = client.get(f"/investors/{investor_id}/contacts").json()
        assert len(remaining) == 2

    def test_refuses_even_when_it_is_the_only_contact(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        primary = _seed_contact(investor_id, first_name="Ada", is_primary=True)
        self._as_fund_manager(override_user, org_id)

        assert (
            client.delete(f"/investors/{investor_id}/contacts/{primary}").status_code
            == 409
        )

    def test_deletable_once_another_contact_is_promoted(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        was_primary = _seed_contact(investor_id, first_name="Ada", is_primary=True)
        other = _seed_contact(investor_id, first_name="Sam", is_primary=False)
        self._as_fund_manager(override_user, org_id)

        # Promoting Sam clears Ada's flag, which unblocks the deletion.
        promoted = client.patch(
            f"/investors/{investor_id}/contacts/{other}",
            json={"is_primary": True},
        )
        assert promoted.status_code == 200

        response = client.delete(f"/investors/{investor_id}/contacts/{was_primary}")
        assert response.status_code == 200

    def test_lp_cannot_delete(self, client, override_user):
        org_id = _seed_org()
        investor_id = _seed_investor(org_id)
        contact_id = _seed_contact(investor_id, is_primary=False)
        _seed_user("hanko-lp", UserRole.lp, organization_id=org_id)
        override_user("hanko-lp")

        response = client.delete(f"/investors/{investor_id}/contacts/{contact_id}")
        assert response.status_code == 403


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
