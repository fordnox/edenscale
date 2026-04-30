"""Unit tests for the ``UserOrganizationMembership`` ORM model.

Covers the relationship round-trip (User <-> Membership <-> Organization)
and the ``uq_user_org_membership`` unique constraint that blocks duplicate
``(user_id, organization_id)`` pairs.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import Base, SessionLocal, engine
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


def _seed_user_and_org(
    *,
    email: str = "alice@example.com",
    org_name: str = "Eden Capital",
) -> tuple[int, int]:
    db = SessionLocal()
    try:
        org = Organization(name=org_name, type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.flush()
        user = User(
            organization_id=org.id,
            role=UserRole.fund_manager,
            first_name="Alice",
            last_name="Liddell",
            email=email,
            hanko_subject_id=email,
        )
        db.add(user)
        db.commit()
        return user.id, org.id
    finally:
        db.close()


class TestMembershipRelationships:
    def test_create_membership_round_trips_relationships(self):
        user_id, org_id = _seed_user_and_org()
        db = SessionLocal()
        try:
            membership = UserOrganizationMembership(
                user_id=user_id,
                organization_id=org_id,
                role=UserRole.admin,
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)

            assert membership.id is not None
            assert membership.role is UserRole.admin
            assert membership.created_at is not None
            assert membership.updated_at is not None

            assert membership.user.id == user_id
            assert membership.organization.id == org_id

            user = db.get(User, user_id)
            org = db.get(Organization, org_id)
            assert [m.id for m in user.memberships] == [membership.id]
            assert [m.id for m in org.memberships] == [membership.id]
        finally:
            db.close()

    def test_user_can_have_memberships_in_multiple_orgs(self):
        user_id, first_org_id = _seed_user_and_org()
        db = SessionLocal()
        try:
            second_org = Organization(
                name="Second Capital", type=OrganizationType.fund_manager_firm
            )
            db.add(second_org)
            db.flush()
            db.add_all(
                [
                    UserOrganizationMembership(
                        user_id=user_id,
                        organization_id=first_org_id,
                        role=UserRole.admin,
                    ),
                    UserOrganizationMembership(
                        user_id=user_id,
                        organization_id=second_org.id,
                        role=UserRole.fund_manager,
                    ),
                ]
            )
            db.commit()

            user = db.get(User, user_id)
            org_ids = sorted(m.organization_id for m in user.memberships)
            assert org_ids == sorted([first_org_id, second_org.id])
        finally:
            db.close()


class TestMembershipUniqueConstraint:
    def test_duplicate_user_org_pair_is_rejected(self):
        user_id, org_id = _seed_user_and_org()
        db = SessionLocal()
        try:
            db.add(
                UserOrganizationMembership(
                    user_id=user_id,
                    organization_id=org_id,
                    role=UserRole.admin,
                )
            )
            db.commit()

            db.add(
                UserOrganizationMembership(
                    user_id=user_id,
                    organization_id=org_id,
                    role=UserRole.fund_manager,
                )
            )
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        finally:
            db.close()
