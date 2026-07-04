"""Tests for the /users router."""

import pytest
from fastapi.testclient import TestClient
from app.core.slugs import slugify

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
        return str(user.id)
    finally:
        db.close()


def _seed_invited_member(
    subject_id: str,
    organization_id: str,
    role: UserRole,
    *,
    email: str | None = None,
) -> str:
    """A user in the state invitation acceptance leaves them in: provisioned
    via Hanko (global ``role`` lp) with their org role living only on the
    membership row."""
    db = SessionLocal()
    try:
        user = User(
            role=UserRole.lp,
            first_name="Invited",
            last_name="Member",
            email=email or f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
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


def _get_membership_role(user_id: str, organization_id: str) -> UserRole:
    db = SessionLocal()
    try:
        membership = (
            db.query(UserOrganizationMembership)
            .filter(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.organization_id == organization_id,
            )
            .one()
        )
        return membership.role
    finally:
        db.close()


def _seed_org(name: str = "NewTaven Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return str(org.id)
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
        assert data["first_name"] == "Margot"
        assert data["last_name"] == "Lane"

    def test_get_me_auto_provisions_unknown_subject_as_lp(self, client, override_user):
        override_user("hanko-fresh")
        response = client.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "lp"
        assert data["hanko_subject_id"] == "hanko-fresh"


class TestListUsers:
    def test_invited_member_is_listed_with_membership_role(
        self, client, override_user
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        invitee_id = _seed_invited_member(
            "hanko-invitee", org_id, UserRole.fund_manager
        )

        override_user("hanko-admin")
        response = client.get("/users")

        assert response.status_code == 200
        rows = {row["id"]: row for row in response.json()}
        assert invitee_id in rows
        assert rows[invitee_id]["role"] == "fund_manager"

    def test_members_of_other_organizations_are_not_listed(
        self, client, override_user
    ):
        org_id = _seed_org()
        other_org_id = _seed_org("Other Firm")
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        outsider_id = _seed_user(
            "hanko-outsider",
            UserRole.admin,
            email="outsider@example.com",
            organization_id=other_org_id,
        )

        override_user("hanko-admin")
        response = client.get("/users")

        assert response.status_code == 200
        assert outsider_id not in {row["id"] for row in response.json()}


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
        assert _get_membership_role(target_id, org_id) is UserRole.fund_manager

    def test_role_change_updates_invited_members_membership(
        self, client, override_user
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        invitee_id = _seed_invited_member("hanko-invitee", org_id, UserRole.lp)

        override_user("hanko-admin")
        response = client.patch(
            f"/users/{invitee_id}/role", json={"role": "fund_manager"}
        )

        assert response.status_code == 200
        assert response.json()["role"] == "fund_manager"
        assert _get_membership_role(invitee_id, org_id) is UserRole.fund_manager

    def test_cannot_change_role_of_non_member(self, client, override_user):
        org_id = _seed_org()
        other_org_id = _seed_org("Other Firm")
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        outsider_id = _seed_user(
            "hanko-outsider",
            UserRole.lp,
            email="outsider@example.com",
            organization_id=other_org_id,
        )

        override_user("hanko-admin")
        response = client.patch(
            f"/users/{outsider_id}/role", json={"role": "admin"}
        )

        assert response.status_code == 404
        assert _get_membership_role(outsider_id, other_org_id) is UserRole.lp
