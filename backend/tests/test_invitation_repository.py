"""Unit tests for ``OrganizationInvitationRepository``.

Covers create / lookup / list / mark / rotate / expire helpers. ``expire_stale``
must be idempotent and must not flip already-accepted or already-revoked rows.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import Base, SessionLocal, engine
from app.models import (
    Organization,
    OrganizationInvitation,
    OrganizationType,
    User,
    UserRole,
)
from app.models.enums import InvitationStatus
from app.repositories.organization_invitation_repository import (
    OrganizationInvitationRepository,
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


def _seed_org(db, name: str = "Eden Capital") -> int:
    org = Organization(name=name, type=OrganizationType.fund_manager_firm)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org.id


def _seed_user(db, email: str, role: UserRole = UserRole.admin) -> int:
    user = User(
        role=role,
        first_name="First",
        last_name="Last",
        email=email,
        hanko_subject_id=email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


class TestCreateAndLookup:
    def test_create_persists_with_pending_status_and_unique_token(self, db):
        org_id = _seed_org(db)
        inviter_id = _seed_user(db, "inviter@example.com")
        repo = OrganizationInvitationRepository(db)

        first = repo.create(
            organization_id=org_id,
            email="invitee@example.com",
            role=UserRole.lp,
            invited_by_user_id=inviter_id,
        )
        second = repo.create(
            organization_id=org_id,
            email="another@example.com",
            role=UserRole.fund_manager,
            invited_by_user_id=inviter_id,
        )

        assert first.id is not None
        assert first.status is InvitationStatus.pending
        assert first.token and len(first.token) >= 32
        assert first.expires_at is not None
        # Default expiry is ~14 days out.
        expires = first.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        delta = expires - datetime.now(timezone.utc)
        assert timedelta(days=13) <= delta <= timedelta(days=15)

        assert first.token != second.token

    def test_create_allows_null_invited_by_for_superadmin(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)

        invitation = repo.create(
            organization_id=org_id,
            email="lonely@example.com",
            role=UserRole.admin,
            invited_by_user_id=None,
        )

        assert invitation.invited_by_user_id is None

    def test_get_returns_row_or_none(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)

        invitation = repo.create(
            organization_id=org_id,
            email="invitee@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )

        assert repo.get(invitation.id).id == invitation.id
        assert repo.get(99999) is None

    def test_get_by_token_returns_row_or_none(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)

        invitation = repo.create(
            organization_id=org_id,
            email="invitee@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )

        assert repo.get_by_token(invitation.token).id == invitation.id
        assert repo.get_by_token("nope") is None


class TestLists:
    def test_list_for_organization_filters_to_org_and_orders_desc(self, db):
        org_a = _seed_org(db, "Org A")
        org_b = _seed_org(db, "Org B")
        repo = OrganizationInvitationRepository(db)

        a1 = repo.create(
            organization_id=org_a,
            email="a1@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )
        a2 = repo.create(
            organization_id=org_a,
            email="a2@example.com",
            role=UserRole.fund_manager,
            invited_by_user_id=None,
        )
        repo.create(
            organization_id=org_b,
            email="b1@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )

        rows = repo.list_for_organization(org_a)
        assert [r.id for r in rows] == [a2.id, a1.id]

    def test_list_for_organization_with_status_filter(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)

        pending = repo.create(
            organization_id=org_id,
            email="p@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )
        revoked_invite = repo.create(
            organization_id=org_id,
            email="r@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )
        repo.mark_revoked(revoked_invite.id)

        pending_rows = repo.list_for_organization(
            org_id, status=InvitationStatus.pending
        )
        revoked_rows = repo.list_for_organization(
            org_id, status=InvitationStatus.revoked
        )

        assert [r.id for r in pending_rows] == [pending.id]
        assert [r.id for r in revoked_rows] == [revoked_invite.id]

    def test_list_pending_for_email_only_returns_pending(self, db):
        org_a = _seed_org(db, "Org A")
        org_b = _seed_org(db, "Org B")
        repo = OrganizationInvitationRepository(db)

        target = "match@example.com"
        first = repo.create(
            organization_id=org_a,
            email=target,
            role=UserRole.lp,
            invited_by_user_id=None,
        )
        second = repo.create(
            organization_id=org_b,
            email=target,
            role=UserRole.admin,
            invited_by_user_id=None,
        )
        accepted = repo.create(
            organization_id=org_a,
            email=target,
            role=UserRole.lp,
            invited_by_user_id=None,
        )
        repo.mark_accepted(accepted.id)
        repo.create(
            organization_id=org_a,
            email="other@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )

        rows = repo.list_pending_for_email(target)
        assert {r.id for r in rows} == {first.id, second.id}


class TestStatusTransitions:
    def test_mark_accepted_sets_status_and_timestamp(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)
        invitation = repo.create(
            organization_id=org_id,
            email="x@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )

        accepted = repo.mark_accepted(invitation.id)

        assert accepted is not None
        assert accepted.status is InvitationStatus.accepted
        assert accepted.accepted_at is not None

    def test_mark_accepted_returns_none_for_unknown(self, db):
        repo = OrganizationInvitationRepository(db)
        assert repo.mark_accepted(99999) is None

    def test_mark_revoked_flips_status(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)
        invitation = repo.create(
            organization_id=org_id,
            email="x@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )

        revoked = repo.mark_revoked(invitation.id)
        assert revoked is not None
        assert revoked.status is InvitationStatus.revoked

    def test_mark_revoked_returns_none_for_unknown(self, db):
        repo = OrganizationInvitationRepository(db)
        assert repo.mark_revoked(99999) is None

    def test_rotate_token_issues_new_token(self, db):
        org_id = _seed_org(db)
        repo = OrganizationInvitationRepository(db)
        invitation = repo.create(
            organization_id=org_id,
            email="x@example.com",
            role=UserRole.lp,
            invited_by_user_id=None,
        )
        original_token = invitation.token

        rotated = repo.rotate_token(invitation.id)

        assert rotated is not None
        assert rotated.token != original_token
        # Old token must no longer resolve.
        assert repo.get_by_token(original_token) is None
        assert repo.get_by_token(rotated.token).id == invitation.id

    def test_rotate_token_returns_none_for_unknown(self, db):
        repo = OrganizationInvitationRepository(db)
        assert repo.rotate_token(99999) is None


class TestExpireStale:
    def _seed_with_expiry(
        self,
        db,
        org_id: int,
        email: str,
        expires_at: datetime,
        status: InvitationStatus = InvitationStatus.pending,
    ) -> int:
        invitation = OrganizationInvitation(
            organization_id=org_id,
            email=email,
            role=UserRole.lp,
            token=f"token-{email}",
            status=status,
            expires_at=expires_at,
            invited_by_user_id=None,
        )
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        return invitation.id

    def test_flips_only_pending_rows_in_the_past(self, db):
        org_id = _seed_org(db)
        now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        past = now - timedelta(days=1)
        future = now + timedelta(days=1)

        stale_id = self._seed_with_expiry(db, org_id, "stale@example.com", past)
        fresh_id = self._seed_with_expiry(db, org_id, "fresh@example.com", future)
        accepted_id = self._seed_with_expiry(
            db, org_id, "done@example.com", past, status=InvitationStatus.accepted
        )
        revoked_id = self._seed_with_expiry(
            db, org_id, "gone@example.com", past, status=InvitationStatus.revoked
        )

        repo = OrganizationInvitationRepository(db)
        updated = repo.expire_stale(now=now)

        assert updated == 1
        # Need a fresh fetch because the bulk update used
        # synchronize_session=False.
        db.expire_all()
        assert repo.get(stale_id).status is InvitationStatus.expired
        assert repo.get(fresh_id).status is InvitationStatus.pending
        assert repo.get(accepted_id).status is InvitationStatus.accepted
        assert repo.get(revoked_id).status is InvitationStatus.revoked

    def test_is_idempotent_on_second_call(self, db):
        org_id = _seed_org(db)
        now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        self._seed_with_expiry(
            db, org_id, "stale@example.com", now - timedelta(days=1)
        )

        repo = OrganizationInvitationRepository(db)
        first = repo.expire_stale(now=now)
        second = repo.expire_stale(now=now)

        assert first == 1
        assert second == 0

    def test_default_now_uses_current_utc(self, db):
        """Calling without ``now`` should still flip rows that are clearly in
        the past — guards against accidental sign flips in the helper."""
        org_id = _seed_org(db)
        ancient = datetime(2020, 1, 1, tzinfo=timezone.utc)
        stale_id = self._seed_with_expiry(db, org_id, "old@example.com", ancient)

        repo = OrganizationInvitationRepository(db)
        updated = repo.expire_stale()

        assert updated == 1
        db.expire_all()
        assert repo.get(stale_id).status is InvitationStatus.expired
