"""Integration tests for the /organizations router."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import Organization, OrganizationType, User, UserRole


@pytest.fixture(autouse=True)
def configure_superadmin(monkeypatch):
    """Superadmins are config-defined; register the email these tests
    sign superadmins in with."""
    monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "super@example.com")


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


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
        db.commit()
        return str(user.id)
    finally:
        db.close()


def _seed_org(name: str = "NewTaven Capital", *, is_demo: bool = False) -> int:
    db = SessionLocal()
    try:
        org = Organization(
            name=name,
            slug=slugify(name),
            type=OrganizationType.fund_manager_firm,
            is_demo=is_demo,
        )
        db.add(org)
        db.commit()
        return str(org.id)
    finally:
        db.close()


class TestLegacyOrganizationMutationsRemoved:
    def test_superadmin_must_use_superadmin_create_route(self, client, override_user):
        _seed_user("hanko-super", UserRole.superadmin, email="super@example.com")
        override_user("hanko-super")

        create_response = client.post(
            "/organizations",
            json={
                "type": "fund_manager_firm",
                "name": "Adminco",
                "legal_name": "Adminco LLC",
            },
        )
        assert create_response.status_code == 405

    def test_admin_cannot_create(self, client, override_user):
        _seed_user("hanko-admin", UserRole.admin, email="admin@example.com")
        override_user("hanko-admin")

        response = client.post(
            "/organizations",
            json={"type": "fund_manager_firm", "name": "Adminco"},
        )
        assert response.status_code == 405

    def test_lp_cannot_create(self, client, override_user):
        _seed_user("hanko-lp", UserRole.lp, email="lp@example.com")
        override_user("hanko-lp")

        response = client.post(
            "/organizations",
            json={"type": "investor_firm", "name": "Lpco"},
        )
        assert response.status_code == 405


class TestSelfServeCreateOrganization:
    def test_lp_with_no_org_can_create_and_becomes_admin(self, client, override_user):
        _seed_user("hanko-newcomer", UserRole.lp, email="newcomer@example.com")
        override_user("hanko-newcomer")

        response = client.post(
            "/organizations/self-serve",
            json={"name": "Newcomer Capital", "legal_name": "Newcomer Capital LLC"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["role"] == "admin"
        assert body["organization"]["name"] == "Newcomer Capital"
        assert body["organization"]["type"] == "fund_manager_firm"
        assert body["organization"]["slug"] == "newcomer-capital"

        memberships_response = client.get("/users/me/memberships")
        assert memberships_response.status_code == 200
        memberships = memberships_response.json()
        assert len(memberships) == 1
        assert memberships[0]["organization_id"] == body["organization_id"]
        assert memberships[0]["role"] == "admin"

    def test_user_already_in_an_org_can_self_serve_a_second_one(
        self, client, override_user
    ):
        org_id = _seed_org("Existing Co")
        _seed_user(
            "hanko-existing",
            UserRole.fund_manager,
            email="existing@example.com",
            organization_id=org_id,
        )
        override_user("hanko-existing")

        response = client.post(
            "/organizations/self-serve",
            json={"name": "Side Fund"},
        )
        assert response.status_code == 201
        assert response.json()["organization"]["name"] == "Side Fund"


class TestDemoOrganization:
    def test_get_demo_returns_null_when_none_seeded(self, client, override_user):
        _seed_user("hanko-lp", UserRole.lp, email="lp@example.com")
        override_user("hanko-lp")

        response = client.get("/organizations/demo")
        assert response.status_code == 200
        assert response.json() is None

    def test_get_demo_returns_the_flagged_org(self, client, override_user):
        demo_id = _seed_org("Demo Capital", is_demo=True)
        _seed_org("Regular Capital")
        _seed_user("hanko-lp", UserRole.lp, email="lp@example.com")
        override_user("hanko-lp")

        response = client.get("/organizations/demo")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == demo_id
        assert body["is_demo"] is True

    def test_join_demo_creates_fund_manager_membership(self, client, override_user):
        demo_id = _seed_org("Demo Capital", is_demo=True)
        _seed_user("hanko-newcomer", UserRole.lp, email="newcomer@example.com")
        override_user("hanko-newcomer")

        response = client.post("/organizations/demo/join")
        assert response.status_code == 201
        body = response.json()
        assert body["organization_id"] == demo_id
        assert body["role"] == "fund_manager"
        assert body["organization"]["is_demo"] is True

        memberships_response = client.get("/users/me/memberships")
        assert memberships_response.status_code == 200
        memberships = memberships_response.json()
        assert len(memberships) == 1
        assert memberships[0]["organization_id"] == demo_id

    def test_join_demo_is_idempotent(self, client, override_user):
        _seed_org("Demo Capital", is_demo=True)
        _seed_user("hanko-newcomer", UserRole.lp, email="newcomer@example.com")
        override_user("hanko-newcomer")

        first = client.post("/organizations/demo/join")
        second = client.post("/organizations/demo/join")
        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["id"] == first.json()["id"]

        memberships = client.get("/users/me/memberships").json()
        assert len(memberships) == 1

    def test_join_demo_404s_when_none_seeded(self, client, override_user):
        _seed_user("hanko-newcomer", UserRole.lp, email="newcomer@example.com")
        override_user("hanko-newcomer")

        response = client.post("/organizations/demo/join")
        assert response.status_code == 404


class TestListAndReadOrganization:
    def test_fund_manager_can_read(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        list_response = client.get("/organizations")
        assert list_response.status_code == 405

        get_response = client.get(f"/organizations/{org_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == org_id


class TestDeleteOrganization:
    def test_fund_manager_cannot_delete(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.delete(f"/organizations/{org_id}")
        assert response.status_code == 405

    def test_admin_cannot_delete(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-admin", UserRole.admin, email="admin@example.com")
        override_user("hanko-admin")

        response = client.delete(f"/organizations/{org_id}")
        assert response.status_code == 405

    def test_superadmin_must_use_superadmin_disable_route(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-super", UserRole.superadmin, email="super@example.com")
        override_user("hanko-super")

        response = client.delete(f"/organizations/{org_id}")
        assert response.status_code == 405
