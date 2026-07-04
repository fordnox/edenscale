"""Unit tests for ``UserOrganizationMembershipRepository``."""

import uuid
from app.core.slugs import slugify

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


def _seed_org(name: str = "NewTaven Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


def _seed_user(
    email: str,
    role: UserRole = UserRole.fund_manager,
) -> int:
    db = SessionLocal()
    try:
        user = User(
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
        user_id = _seed_user("multi@example.com")
        other_id = _seed_user("other@example.com")

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
        a = _seed_user("a@example.com")
        b = _seed_user("b@example.com")

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
        user_id = _seed_user("a@example.com")

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
            assert repo.update_role(uuid.uuid4(), UserRole.admin) is None
        finally:
            db.close()


class TestDelete:
    def test_delete_removes_membership(self):
        org_id = _seed_org()
        user_id = _seed_user("a@example.com")

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
            assert repo.delete(uuid.uuid4()) is None
        finally:
            db.close()
