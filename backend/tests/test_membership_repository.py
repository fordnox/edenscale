"""Unit tests for ``UserOrganizationMembershipRepository``.

Covers list/update/delete plus the ``bulk_seed_from_legacy_user_org_id``
backfill helper that powers the alembic migration. The backfill must be
idempotent so re-running it (during partial migrations or tests) doesn't
duplicate rows.
"""

import pytest

from app.core.database import Base, SessionLocal, engine
from app.models import (
    Organization,
    OrganizationType,
    User,
    UserOrganizationMembership,
    UserRole,
)
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
    email: str,
    role: UserRole = UserRole.fund_manager,
    organization_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        user = User(
            organization_id=organization_id,
            role=role,
            first_name="First",
            last_name="Last",
            email=email,
            hanko_subject_id=email,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


class TestListAndGet:
    def test_list_for_user_returns_all_memberships_for_that_user(self):
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        user_id = _seed_user("multi@example.com", organization_id=org_a)
        other_id = _seed_user("other@example.com", organization_id=org_a)

        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            repo.create(user_id, org_a, UserRole.admin)
            repo.create(user_id, org_b, UserRole.fund_manager)
            repo.create(other_id, org_a, UserRole.lp)

            memberships = repo.list_for_user(user_id)
            assert sorted(m.organization_id for m in memberships) == sorted(
                [org_a, org_b]
            )
        finally:
            db.close()

    def test_list_for_organization_returns_all_members(self):
        org_id = _seed_org()
        a = _seed_user("a@example.com", organization_id=org_id)
        b = _seed_user("b@example.com", organization_id=org_id)

        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            repo.create(a, org_id, UserRole.admin)
            repo.create(b, org_id, UserRole.lp)

            memberships = repo.list_for_organization(org_id)
            assert sorted(m.user_id for m in memberships) == sorted([a, b])
        finally:
            db.close()


class TestUpdateRole:
    def test_update_role_changes_role_and_returns_membership(self):
        org_id = _seed_org()
        user_id = _seed_user("a@example.com", organization_id=org_id)

        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            membership = repo.create(user_id, org_id, UserRole.lp)

            updated = repo.update_role(membership.id, UserRole.admin)
            assert updated is not None
            assert updated.role is UserRole.admin

            refetched = repo.get(user_id, org_id)
            assert refetched is not None
            assert refetched.role is UserRole.admin
        finally:
            db.close()

    def test_update_role_returns_none_for_unknown_membership(self):
        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            assert repo.update_role(9999, UserRole.admin) is None
        finally:
            db.close()


class TestDelete:
    def test_delete_removes_membership(self):
        org_id = _seed_org()
        user_id = _seed_user("a@example.com", organization_id=org_id)

        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            membership = repo.create(user_id, org_id, UserRole.lp)

            deleted = repo.delete(membership.id)
            assert deleted is not None
            assert repo.get(user_id, org_id) is None
        finally:
            db.close()

    def test_delete_returns_none_for_unknown_membership(self):
        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            assert repo.delete(9999) is None
        finally:
            db.close()


class TestBulkSeedFromLegacy:
    def test_seeds_membership_for_each_user_with_legacy_org_id(self):
        org_id = _seed_org()
        a = _seed_user("a@example.com", role=UserRole.admin, organization_id=org_id)
        b = _seed_user(
            "b@example.com", role=UserRole.fund_manager, organization_id=org_id
        )
        # User without org should be skipped.
        c = _seed_user("c@example.com", role=UserRole.lp, organization_id=None)

        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            inserted = repo.bulk_seed_from_legacy_user_org_id()

            assert inserted == 2
            rows = (
                db.query(UserOrganizationMembership)
                .order_by(UserOrganizationMembership.user_id)
                .all()
            )
            assert {(r.user_id, r.organization_id, r.role) for r in rows} == {
                (a, org_id, UserRole.admin),
                (b, org_id, UserRole.fund_manager),
            }
            assert all(r.user_id != c for r in rows)
        finally:
            db.close()

    def test_is_idempotent_on_second_call(self):
        org_id = _seed_org()
        _seed_user("a@example.com", organization_id=org_id)
        _seed_user("b@example.com", organization_id=org_id)

        db = SessionLocal()
        try:
            repo = UserOrganizationMembershipRepository(db)
            first = repo.bulk_seed_from_legacy_user_org_id()
            second = repo.bulk_seed_from_legacy_user_org_id()

            assert first == 2
            assert second == 0
            assert db.query(UserOrganizationMembership).count() == 2
        finally:
            db.close()
