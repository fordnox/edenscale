"""Unit tests for ``get_active_membership`` and ``require_membership_roles``.

The dependency resolves which ``UserOrganizationMembership`` the caller is
acting through, given an optional ``X-Organization-Id`` header. These tests
exercise it directly with the SQLAlchemy session — no FastAPI client needed —
mirroring ``test_rbac.py``.
"""

import pytest
from fastapi import HTTPException

from app.core.database import Base, SessionLocal, engine
from app.core.rbac import get_active_membership, require_membership_roles
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
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_org(db, name: str = "Eden Capital") -> Organization:
    org = Organization(name=name, type=OrganizationType.fund_manager_firm)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _seed_user(db, role: UserRole, *, email: str, subject_id: str) -> User:
    user = User(
        role=role,
        first_name="First",
        last_name="Last",
        email=email,
        hanko_subject_id=subject_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_membership(
    db, user_id: int, organization_id: int, role: UserRole
) -> UserOrganizationMembership:
    membership = UserOrganizationMembership(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def test_header_missing_with_single_membership_resolves(db):
    org = _seed_org(db)
    user = _seed_user(
        db, UserRole.fund_manager, email="fm@example.com", subject_id="hanko-fm"
    )
    membership = _seed_membership(db, user.id, org.id, UserRole.fund_manager)

    resolved = get_active_membership(
        x_organization_id=None, current_user=user, db=db
    )

    assert resolved.id == membership.id
    assert resolved.organization_id == org.id
    assert resolved.role is UserRole.fund_manager


def test_header_present_with_matching_membership_resolves(db):
    org_a = _seed_org(db, "Org A")
    org_b = _seed_org(db, "Org B")
    user = _seed_user(
        db, UserRole.lp, email="multi@example.com", subject_id="hanko-multi"
    )
    _seed_membership(db, user.id, org_a.id, UserRole.lp)
    membership_b = _seed_membership(db, user.id, org_b.id, UserRole.admin)

    resolved = get_active_membership(
        x_organization_id=org_b.id, current_user=user, db=db
    )

    assert resolved.id == membership_b.id
    assert resolved.organization_id == org_b.id
    assert resolved.role is UserRole.admin


def test_header_present_no_match_for_non_superadmin_returns_403(db):
    org_a = _seed_org(db, "Org A")
    org_b = _seed_org(db, "Org B")
    user = _seed_user(
        db, UserRole.fund_manager, email="fm@example.com", subject_id="hanko-fm"
    )
    _seed_membership(db, user.id, org_a.id, UserRole.fund_manager)

    with pytest.raises(HTTPException) as excinfo:
        get_active_membership(
            x_organization_id=org_b.id, current_user=user, db=db
        )

    assert excinfo.value.status_code == 403
    assert "Not a member" in excinfo.value.detail


def test_header_present_for_superadmin_synthesizes_membership(db):
    org = _seed_org(db, "Foreign Org")
    superadmin = _seed_user(
        db,
        UserRole.superadmin,
        email="root@example.com",
        subject_id="hanko-root",
    )

    resolved = get_active_membership(
        x_organization_id=org.id, current_user=superadmin, db=db
    )

    assert resolved.user_id == superadmin.id
    assert resolved.organization_id == org.id
    assert resolved.role is UserRole.superadmin
    # Synthesized — never persisted to the DB.
    assert resolved.id is None
    assert (
        db.query(UserOrganizationMembership)
        .filter(
            UserOrganizationMembership.user_id == superadmin.id,
            UserOrganizationMembership.organization_id == org.id,
        )
        .first()
        is None
    )


def test_header_present_for_superadmin_with_real_membership_returns_real_row(db):
    """When a superadmin happens to also have a real membership row for the
    given org, the dep returns the persisted row rather than synthesizing —
    so audit-relevant data (membership.id, role) reflects reality."""
    org = _seed_org(db)
    superadmin = _seed_user(
        db,
        UserRole.superadmin,
        email="root@example.com",
        subject_id="hanko-root",
    )
    real = _seed_membership(db, superadmin.id, org.id, UserRole.admin)

    resolved = get_active_membership(
        x_organization_id=org.id, current_user=superadmin, db=db
    )

    assert resolved.id == real.id
    assert resolved.role is UserRole.admin


def test_header_missing_for_superadmin_returns_400(db):
    superadmin = _seed_user(
        db,
        UserRole.superadmin,
        email="root@example.com",
        subject_id="hanko-root",
    )

    with pytest.raises(HTTPException) as excinfo:
        get_active_membership(
            x_organization_id=None, current_user=superadmin, db=db
        )

    assert excinfo.value.status_code == 400
    assert "X-Organization-Id" in excinfo.value.detail


def test_header_missing_with_multiple_memberships_returns_400(db):
    org_a = _seed_org(db, "Org A")
    org_b = _seed_org(db, "Org B")
    user = _seed_user(
        db, UserRole.lp, email="multi@example.com", subject_id="hanko-multi"
    )
    _seed_membership(db, user.id, org_a.id, UserRole.lp)
    _seed_membership(db, user.id, org_b.id, UserRole.admin)

    with pytest.raises(HTTPException) as excinfo:
        get_active_membership(
            x_organization_id=None, current_user=user, db=db
        )

    assert excinfo.value.status_code == 400
    assert "X-Organization-Id" in excinfo.value.detail


def test_header_missing_with_zero_memberships_returns_400(db):
    user = _seed_user(
        db, UserRole.lp, email="solo@example.com", subject_id="hanko-solo"
    )

    with pytest.raises(HTTPException) as excinfo:
        get_active_membership(
            x_organization_id=None, current_user=user, db=db
        )

    assert excinfo.value.status_code == 400


class TestRequireMembershipRoles:
    def test_allows_matching_membership_role(self, db):
        org = _seed_org(db)
        user = _seed_user(
            db,
            UserRole.lp,
            email="dual@example.com",
            subject_id="hanko-dual",
        )
        # Globally lp, but admin within this org.
        membership = _seed_membership(db, user.id, org.id, UserRole.admin)

        dep = require_membership_roles(UserRole.admin, UserRole.fund_manager)
        assert dep(membership=membership) is membership

    def test_rejects_non_matching_membership_role(self, db):
        org = _seed_org(db)
        user = _seed_user(
            db, UserRole.lp, email="lp@example.com", subject_id="hanko-lp"
        )
        membership = _seed_membership(db, user.id, org.id, UserRole.lp)

        dep = require_membership_roles(UserRole.admin, UserRole.fund_manager)
        with pytest.raises(HTTPException) as excinfo:
            dep(membership=membership)
        assert excinfo.value.status_code == 403

    def test_synthesized_superadmin_membership_passes_when_listed(self, db):
        """A superadmin acting through a synthesized membership has
        ``role=superadmin``; routes that include ``superadmin`` in the
        allow-list let them through."""
        membership = UserOrganizationMembership(
            user_id=1,
            organization_id=1,
            role=UserRole.superadmin,
        )
        dep = require_membership_roles(
            UserRole.admin, UserRole.fund_manager, UserRole.superadmin
        )
        assert dep(membership=membership) is membership
