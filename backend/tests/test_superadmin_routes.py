"""Integration tests for the `/superadmin/*` router.

The router lives at `app.routers.superadmin` and is mounted in `app.main`
behind `Depends(get_current_user)` (JWT only) plus per-route
`require_superadmin`. These tests cover:

* Every route 403s for non-superadmin callers (admin, fund_manager, lp).
* `POST /superadmin/organizations` creates the org + the founding admin
  membership in one transaction, both for an existing user_id and for a
  fresh `admin_email` (stub user is created with `hanko_subject_id=None`).
* `GET /superadmin/organizations` lists active *and* inactive orgs with the
  correct `member_count`.
* `POST /superadmin/organizations/{id}/admins` is idempotent — re-targeting
  an existing membership returns it as-is when already admin, or upgrades
  the role when it was something else.
* `PATCH /disable` and `PATCH /enable` round-trip the `is_active` flag
  without dropping memberships (distinct from `DELETE /organizations/{id}`).
* `GET /superadmin/organizations/{id}/members` returns the roster with
  nested user payloads.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Organization,
    OrganizationType,
    User,
    UserOrganizationMembership,
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


def _seed_org(
    name: str = "Eden Capital",
    *,
    type_: OrganizationType = OrganizationType.fund_manager_firm,
    is_active: bool = True,
) -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=type_, is_active=is_active)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


def _seed_membership(user_id: int, organization_id: int, role: UserRole) -> int:
    db = SessionLocal()
    try:
        m = UserOrganizationMembership(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
        )
        db.add(m)
        db.commit()
        return m.id
    finally:
        db.close()


def _login_as_superadmin(override_user) -> int:
    user_id = _seed_user("hanko-super", UserRole.superadmin, email="super@example.com")
    override_user("hanko-super")
    return user_id


class TestNonSuperadminForbidden:
    """Every `/superadmin/*` endpoint must 403 for non-superadmin callers."""

    @pytest.mark.parametrize(
        "role,subject,email",
        [
            (UserRole.admin, "hanko-admin", "admin@example.com"),
            (UserRole.fund_manager, "hanko-fm", "fm@example.com"),
            (UserRole.lp, "hanko-lp", "lp@example.com"),
        ],
    )
    def test_list_organizations_forbidden(
        self, client, override_user, role, subject, email
    ):
        _seed_user(subject, role, email=email)
        override_user(subject)

        response = client.get("/superadmin/organizations")
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "role,subject,email",
        [
            (UserRole.admin, "hanko-admin", "admin@example.com"),
            (UserRole.fund_manager, "hanko-fm", "fm@example.com"),
            (UserRole.lp, "hanko-lp", "lp@example.com"),
        ],
    )
    def test_create_organization_forbidden(
        self, client, override_user, role, subject, email
    ):
        _seed_user(subject, role, email=email)
        override_user(subject)

        response = client.post(
            "/superadmin/organizations",
            json={
                "type": "fund_manager_firm",
                "name": "Sneaky LLC",
                "admin_email": "newadmin@example.com",
            },
        )
        assert response.status_code == 403

    def test_assign_admin_forbidden(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-admin", UserRole.admin, email="admin@example.com")
        override_user("hanko-admin")

        response = client.post(
            f"/superadmin/organizations/{org_id}/admins",
            json={"email": "promote@example.com"},
        )
        assert response.status_code == 403

    def test_disable_forbidden(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-fm", UserRole.fund_manager, email="fm@example.com")
        override_user("hanko-fm")

        response = client.patch(f"/superadmin/organizations/{org_id}/disable")
        assert response.status_code == 403

    def test_enable_forbidden(self, client, override_user):
        org_id = _seed_org(is_active=False)
        _seed_user("hanko-lp", UserRole.lp, email="lp@example.com")
        override_user("hanko-lp")

        response = client.patch(f"/superadmin/organizations/{org_id}/enable")
        assert response.status_code == 403

    def test_list_members_forbidden(self, client, override_user):
        org_id = _seed_org()
        _seed_user("hanko-admin", UserRole.admin, email="admin@example.com")
        override_user("hanko-admin")

        response = client.get(f"/superadmin/organizations/{org_id}/members")
        assert response.status_code == 403


class TestListOrganizations:
    def test_returns_active_and_inactive_with_member_counts(
        self, client, override_user
    ):
        active_id = _seed_org("Active Co", is_active=True)
        inactive_id = _seed_org("Inactive Co", is_active=False)
        empty_id = _seed_org("Empty Co", is_active=True)

        super_id = _login_as_superadmin(override_user)
        member_one = _seed_user("hanko-m1", UserRole.lp, email="m1@example.com")
        member_two = _seed_user("hanko-m2", UserRole.lp, email="m2@example.com")
        _seed_membership(super_id, active_id, UserRole.admin)
        _seed_membership(member_one, active_id, UserRole.lp)
        _seed_membership(member_two, inactive_id, UserRole.admin)

        response = client.get("/superadmin/organizations")
        assert response.status_code == 200
        rows = response.json()

        by_id = {row["id"]: row for row in rows}
        assert by_id[active_id]["member_count"] == 2
        assert by_id[active_id]["is_active"] is True
        assert by_id[inactive_id]["member_count"] == 1
        assert by_id[inactive_id]["is_active"] is False
        assert by_id[empty_id]["member_count"] == 0
        assert by_id[empty_id]["is_active"] is True

    def test_returns_empty_list_when_no_orgs(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.get("/superadmin/organizations")
        assert response.status_code == 200
        assert response.json() == []


class TestCreateOrganizationWithAdmin:
    def test_creates_org_and_admin_membership_for_existing_user(
        self, client, override_user
    ):
        _login_as_superadmin(override_user)
        existing_user_id = _seed_user(
            "hanko-existing", UserRole.lp, email="existing@example.com"
        )

        response = client.post(
            "/superadmin/organizations",
            json={
                "type": "fund_manager_firm",
                "name": "FreshCo",
                "legal_name": "FreshCo LLC",
                "admin_user_id": existing_user_id,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["organization"]["name"] == "FreshCo"
        assert body["organization"]["is_active"] is True
        assert body["admin_membership"]["user_id"] == existing_user_id
        assert body["admin_membership"]["role"] == "admin"
        assert (
            body["admin_membership"]["organization_id"] == body["organization"]["id"]
        )

        db = SessionLocal()
        try:
            membership = (
                db.query(UserOrganizationMembership)
                .filter(
                    UserOrganizationMembership.user_id == existing_user_id,
                    UserOrganizationMembership.organization_id
                    == body["organization"]["id"],
                )
                .first()
            )
            assert membership is not None
            assert membership.role == UserRole.admin
        finally:
            db.close()

    def test_creates_stub_user_when_admin_email_unknown(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.post(
            "/superadmin/organizations",
            json={
                "type": "investor_firm",
                "name": "StubCo",
                "admin_email": "stub@example.com",
                "admin_first_name": "Stub",
                "admin_last_name": "User",
            },
        )
        assert response.status_code == 201
        body = response.json()

        db = SessionLocal()
        try:
            stub = db.query(User).filter(User.email == "stub@example.com").first()
            assert stub is not None
            assert stub.hanko_subject_id is None
            assert stub.first_name == "Stub"
            assert stub.last_name == "User"
            assert stub.role == UserRole.lp

            membership = (
                db.query(UserOrganizationMembership)
                .filter(
                    UserOrganizationMembership.user_id == stub.id,
                    UserOrganizationMembership.organization_id
                    == body["organization"]["id"],
                )
                .first()
            )
            assert membership is not None
            assert membership.role == UserRole.admin
        finally:
            db.close()

    def test_attaches_admin_membership_when_admin_email_matches_existing_user(
        self, client, override_user
    ):
        _login_as_superadmin(override_user)
        existing_user_id = _seed_user(
            "hanko-existing", UserRole.lp, email="reuse@example.com"
        )

        response = client.post(
            "/superadmin/organizations",
            json={
                "type": "fund_manager_firm",
                "name": "ReuseCo",
                "admin_email": "reuse@example.com",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["admin_membership"]["user_id"] == existing_user_id

        db = SessionLocal()
        try:
            # Existing user row was reused, no duplicate created.
            users = db.query(User).filter(User.email == "reuse@example.com").all()
            assert len(users) == 1
        finally:
            db.close()

    def test_rejects_when_neither_admin_target_supplied(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.post(
            "/superadmin/organizations",
            json={"type": "fund_manager_firm", "name": "BadCo"},
        )
        assert response.status_code == 422

    def test_rejects_when_both_admin_targets_supplied(self, client, override_user):
        _login_as_superadmin(override_user)
        existing_user_id = _seed_user(
            "hanko-existing", UserRole.lp, email="existing@example.com"
        )

        response = client.post(
            "/superadmin/organizations",
            json={
                "type": "fund_manager_firm",
                "name": "BadCo",
                "admin_user_id": existing_user_id,
                "admin_email": "other@example.com",
            },
        )
        assert response.status_code == 422

    def test_404_when_admin_user_id_missing(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.post(
            "/superadmin/organizations",
            json={
                "type": "fund_manager_firm",
                "name": "GhostCo",
                "admin_user_id": 9999,
            },
        )
        assert response.status_code == 404


class TestAssignOrganizationAdmin:
    def test_creates_admin_membership_for_existing_user(self, client, override_user):
        _login_as_superadmin(override_user)
        org_id = _seed_org("Roster Co")
        target_id = _seed_user("hanko-target", UserRole.lp, email="target@example.com")

        response = client.post(
            f"/superadmin/organizations/{org_id}/admins",
            json={"user_id": target_id},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == target_id
        assert body["organization_id"] == org_id
        assert body["role"] == "admin"

    def test_idempotent_when_user_is_already_admin(self, client, override_user):
        _login_as_superadmin(override_user)
        org_id = _seed_org()
        target_id = _seed_user("hanko-target", UserRole.lp, email="target@example.com")
        membership_id = _seed_membership(target_id, org_id, UserRole.admin)

        response = client.post(
            f"/superadmin/organizations/{org_id}/admins",
            json={"user_id": target_id},
        )
        assert response.status_code == 200
        assert response.json()["id"] == membership_id

        db = SessionLocal()
        try:
            count = (
                db.query(UserOrganizationMembership)
                .filter(
                    UserOrganizationMembership.user_id == target_id,
                    UserOrganizationMembership.organization_id == org_id,
                )
                .count()
            )
            assert count == 1
        finally:
            db.close()

    def test_upgrades_existing_membership_to_admin(self, client, override_user):
        _login_as_superadmin(override_user)
        org_id = _seed_org()
        target_id = _seed_user("hanko-target", UserRole.lp, email="target@example.com")
        membership_id = _seed_membership(target_id, org_id, UserRole.lp)

        response = client.post(
            f"/superadmin/organizations/{org_id}/admins",
            json={"user_id": target_id},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == membership_id
        assert body["role"] == "admin"

        db = SessionLocal()
        try:
            membership = (
                db.query(UserOrganizationMembership)
                .filter(UserOrganizationMembership.id == membership_id)
                .first()
            )
            assert membership.role == UserRole.admin
        finally:
            db.close()

    def test_creates_stub_user_when_email_unknown(self, client, override_user):
        _login_as_superadmin(override_user)
        org_id = _seed_org()

        response = client.post(
            f"/superadmin/organizations/{org_id}/admins",
            json={"email": "fresh@example.com"},
        )
        assert response.status_code == 200

        db = SessionLocal()
        try:
            stub = db.query(User).filter(User.email == "fresh@example.com").first()
            assert stub is not None
            assert stub.hanko_subject_id is None
        finally:
            db.close()

    def test_404_when_organization_missing(self, client, override_user):
        _login_as_superadmin(override_user)
        target_id = _seed_user("hanko-target", UserRole.lp, email="target@example.com")

        response = client.post(
            "/superadmin/organizations/9999/admins",
            json={"user_id": target_id},
        )
        assert response.status_code == 404

    def test_rejects_when_neither_target_supplied(self, client, override_user):
        _login_as_superadmin(override_user)
        org_id = _seed_org()

        response = client.post(
            f"/superadmin/organizations/{org_id}/admins",
            json={},
        )
        assert response.status_code == 422


class TestDisableEnableOrganization:
    def test_disable_then_enable_round_trip(self, client, override_user):
        _login_as_superadmin(override_user)
        org_id = _seed_org()
        member_id = _seed_user("hanko-m", UserRole.lp, email="m@example.com")
        _seed_membership(member_id, org_id, UserRole.lp)

        disable_response = client.patch(
            f"/superadmin/organizations/{org_id}/disable"
        )
        assert disable_response.status_code == 200
        assert disable_response.json()["is_active"] is False

        enable_response = client.patch(f"/superadmin/organizations/{org_id}/enable")
        assert enable_response.status_code == 200
        assert enable_response.json()["is_active"] is True

        db = SessionLocal()
        try:
            membership = (
                db.query(UserOrganizationMembership)
                .filter(
                    UserOrganizationMembership.user_id == member_id,
                    UserOrganizationMembership.organization_id == org_id,
                )
                .first()
            )
            assert membership is not None
        finally:
            db.close()

    def test_disable_404_when_org_missing(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.patch("/superadmin/organizations/9999/disable")
        assert response.status_code == 404

    def test_enable_404_when_org_missing(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.patch("/superadmin/organizations/9999/enable")
        assert response.status_code == 404


class TestListOrganizationMembers:
    def test_returns_roster_with_nested_user(self, client, override_user):
        super_id = _login_as_superadmin(override_user)
        org_id = _seed_org()
        member_one = _seed_user(
            "hanko-m1", UserRole.lp, email="member1@example.com"
        )
        member_two = _seed_user(
            "hanko-m2", UserRole.fund_manager, email="member2@example.com"
        )
        _seed_membership(super_id, org_id, UserRole.admin)
        _seed_membership(member_one, org_id, UserRole.lp)
        _seed_membership(member_two, org_id, UserRole.fund_manager)

        response = client.get(f"/superadmin/organizations/{org_id}/members")
        assert response.status_code == 200
        rows = response.json()

        assert len(rows) == 3
        by_user = {row["user_id"]: row for row in rows}
        assert by_user[member_one]["role"] == "lp"
        assert by_user[member_one]["user"]["email"] == "member1@example.com"
        assert by_user[member_two]["role"] == "fund_manager"
        assert by_user[member_two]["user"]["email"] == "member2@example.com"

    def test_404_when_organization_missing(self, client, override_user):
        _login_as_superadmin(override_user)

        response = client.get("/superadmin/organizations/9999/members")
        assert response.status_code == 404
