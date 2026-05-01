"""Integration tests for the /organizations router."""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Organization, OrganizationType, User, UserRole


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


def _seed_org(name: str = "Eden Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


class TestCreateOrganization:
    def test_superadmin_can_create_and_read(self, client, override_user):
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
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Adminco"
        assert created["type"] == "fund_manager_firm"
        assert created["is_active"] is True

        get_response = client.get(f"/organizations/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == created["id"]

    def test_admin_cannot_create(self, client, override_user):
        _seed_user("hanko-admin", UserRole.admin, email="admin@example.com")
        override_user("hanko-admin")

        response = client.post(
            "/organizations",
            json={"type": "fund_manager_firm", "name": "Adminco"},
        )
        assert response.status_code == 403

    def test_lp_cannot_create(self, client, override_user):
        _seed_user("hanko-lp", UserRole.lp, email="lp@example.com")
        override_user("hanko-lp")

        response = client.post(
            "/organizations",
            json={"type": "investor_firm", "name": "Lpco"},
        )
        assert response.status_code == 403


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
        assert list_response.status_code == 200
        ids = [row["id"] for row in list_response.json()]
        assert org_id in ids

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
        assert response.status_code == 403

    def test_admin_cannot_delete(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-admin", UserRole.admin, email="admin@example.com")
        override_user("hanko-admin")

        response = client.delete(f"/organizations/{org_id}")
        assert response.status_code == 403

    def test_superadmin_can_delete_soft(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-super", UserRole.superadmin, email="super@example.com")
        override_user("hanko-super")

        response = client.delete(f"/organizations/{org_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False
