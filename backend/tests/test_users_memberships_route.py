"""Integration tests for ``GET /users/me/memberships``.

This is the lookup the Phase 05 frontend org switcher uses to discover which
orgs the signed-in user can switch into. The response is a list of
``MembershipRead`` rows, each with the full nested ``OrganizationRead``
payload and the per-org role (which may differ from ``User.role``).
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


def _seed_org(name: str = "Eden Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


def _seed_user_with_memberships(
    subject_id: str,
    role: UserRole,
    *,
    email: str,
    memberships: list[tuple[int, UserRole]],
) -> int:
    db = SessionLocal()
    try:
        user = User(
            role=role,
            first_name="First",
            last_name="Last",
            email=email,
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        for organization_id, membership_role in memberships:
            db.add(
                UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=organization_id,
                    role=membership_role,
                )
            )
        db.commit()
        return user.id
    finally:
        db.close()


def test_lists_all_memberships_with_nested_org_payload(client, override_user):
    org_a = _seed_org("Org A")
    org_b = _seed_org("Org B")
    _seed_user_with_memberships(
        "hanko-multi",
        UserRole.lp,
        email="multi@example.com",
        memberships=[(org_a, UserRole.lp), (org_b, UserRole.admin)],
    )
    override_user("hanko-multi")

    response = client.get("/users/me/memberships")
    assert response.status_code == 200

    rows = response.json()
    assert len(rows) == 2
    by_org = {row["organization_id"]: row for row in rows}

    assert by_org[org_a]["role"] == "lp"
    assert by_org[org_a]["organization"]["id"] == org_a
    assert by_org[org_a]["organization"]["name"] == "Org A"

    assert by_org[org_b]["role"] == "admin"
    assert by_org[org_b]["organization"]["id"] == org_b
    assert by_org[org_b]["organization"]["name"] == "Org B"


def test_per_org_role_can_differ_from_global_user_role(client, override_user):
    """Global ``User.role`` is ``lp`` but per-org membership role is ``admin``;
    the response must return the per-org role so the org switcher can render
    the right capabilities."""
    org_id = _seed_org("Org Z")
    _seed_user_with_memberships(
        "hanko-dual",
        UserRole.lp,
        email="dual@example.com",
        memberships=[(org_id, UserRole.admin)],
    )
    override_user("hanko-dual")

    response = client.get("/users/me/memberships")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["role"] == "admin"


def test_returns_empty_list_when_user_has_no_memberships(client, override_user):
    _seed_user_with_memberships(
        "hanko-solo",
        UserRole.lp,
        email="solo@example.com",
        memberships=[],
    )
    override_user("hanko-solo")

    response = client.get("/users/me/memberships")
    assert response.status_code == 200
    assert response.json() == []


def test_does_not_require_x_organization_id_header(client, override_user):
    """The endpoint is intentionally non-org-scoped — it's the discovery
    lookup the org switcher uses *before* picking an org. So a user with
    multiple memberships and no header should still get 200, not the 400
    that org-scoped routes raise."""
    org_a = _seed_org("Org A")
    org_b = _seed_org("Org B")
    _seed_user_with_memberships(
        "hanko-multi",
        UserRole.lp,
        email="multi@example.com",
        memberships=[(org_a, UserRole.lp), (org_b, UserRole.admin)],
    )
    override_user("hanko-multi")

    response = client.get("/users/me/memberships")
    assert response.status_code == 200
    assert {row["organization_id"] for row in response.json()} == {org_a, org_b}
