"""Tests for the /users router."""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import Organization, OrganizationType, User, UserRole
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
    """Replace the auth dependency with a fake JWT payload, then clean up."""

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
    first_name: str = "First",
    last_name: str = "Last",
) -> int:
    db = SessionLocal()
    try:
        user = User(
            organization_id=organization_id,
            role=role,
            first_name=first_name,
            last_name=last_name,
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


def _seed_org(name: str = "Eden Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


class TestReadCurrentUser:
    def test_get_me_returns_seeded_user(self, client, override_user):
        org_id = _seed_org()
        user_id = _seed_user(
            "hanko-me",
            UserRole.fund_manager,
            email="me@example.com",
            organization_id=org_id,
            first_name="Margot",
            last_name="Lane",
        )

        override_user("hanko-me")
        response = client.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == "me@example.com"
        assert data["role"] == "fund_manager"
        assert data["organization_id"] == org_id
        assert data["first_name"] == "Margot"
        assert data["last_name"] == "Lane"

    def test_get_me_auto_provisions_unknown_subject_as_lp(self, client, override_user):
        override_user("hanko-fresh")
        response = client.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "lp"
        assert data["hanko_subject_id"] == "hanko-fresh"


class TestUpdateUserRole:
    def test_non_admin_cannot_change_role(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        target_id = _seed_user(
            "hanko-target",
            UserRole.lp,
            email="target@example.com",
            organization_id=org_id,
        )

        override_user("hanko-fm")
        response = client.patch(
            f"/users/{target_id}/role", json={"role": "admin"}
        )

        assert response.status_code == 403

    def test_admin_can_change_role(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        target_id = _seed_user(
            "hanko-target",
            UserRole.lp,
            email="target@example.com",
            organization_id=org_id,
        )

        override_user("hanko-admin")
        response = client.patch(
            f"/users/{target_id}/role", json={"role": "fund_manager"}
        )

        assert response.status_code == 200
        assert response.json()["role"] == "fund_manager"
