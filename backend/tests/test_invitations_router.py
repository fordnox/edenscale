"""Integration tests for the ``/invitations`` router.

The router lives at ``app.routers.invitations`` and is mounted in ``app.main``
behind ``Depends(get_current_user)``. Per-route dependencies handle
membership / superadmin / signed-in checks.

These tests cover:

* ``POST /invitations`` — admin creates an invite, row is persisted, the
  Hanko email service is invoked. Non-admins (fund_manager, lp) are 403.
* Superadmin can invite into any org via ``X-Organization-Id``.
* ``POST /invitations/accept`` — signed-in invitee promotes the invite to a
  membership; second attempt 410s; mismatched email 403s; expired/revoked
  invitations 410.
* ``POST /{id}/revoke`` and ``POST /{id}/resend`` — pending-only invariant,
  cross-org refusal, token rotation.
* ``GET /invitations/pending-for-me`` — matches the JWT email regardless of
  case and only returns pending rows.
* ``GET /invitations`` — non-admin gets 403.

The Hanko service is patched at ``app.routers.invitations.send_invitation_email``
so no HTTP traffic leaves the test process.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Organization,
    OrganizationInvitation,
    OrganizationType,
    User,
    UserOrganizationMembership,
    UserRole,
)
from app.models.enums import InvitationStatus


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

    def _set(subject_id: str | None, *, email: str | None = None) -> None:
        def _payload():
            data: dict = {}
            if subject_id is not None:
                data["sub"] = subject_id
            if email is not None:
                data["email"] = email
            return data

        app.dependency_overrides[get_current_user] = _payload

    yield _set
    app.dependency_overrides.clear()


@pytest.fixture
def hanko_email_mock():
    """Patch the router-level ``send_invitation_email`` reference.

    The router imports the function with ``from app.services.hanko import
    send_invitation_email``, so we patch the binding in the router module.
    Returns ``True`` by default — individual tests can override the
    return value by setting ``mock.return_value`` (after re-wrapping with
    ``AsyncMock`` if they need an async side effect).
    """
    with patch(
        "app.routers.invitations.send_invitation_email",
        new=AsyncMock(return_value=True),
    ) as mock:
        yield mock


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
    subject_id: str,
    role: UserRole,
    *,
    email: str | None = None,
    organization_id: int | None = None,
) -> int:
    """Create a User row + (optionally) a matching membership for the org."""
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


def _seed_membership(user_id: int, organization_id: int, role: UserRole) -> int:
    db = SessionLocal()
    try:
        m = UserOrganizationMembership(
            user_id=user_id, organization_id=organization_id, role=role
        )
        db.add(m)
        db.commit()
        return m.id
    finally:
        db.close()


def _seed_invitation(
    organization_id: int,
    *,
    email: str = "invitee@example.com",
    role: UserRole = UserRole.lp,
    status: InvitationStatus = InvitationStatus.pending,
    token: str = "tok-default",
    expires_at: datetime | None = None,
    invited_by_user_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        invitation = OrganizationInvitation(
            organization_id=organization_id,
            email=email,
            role=role,
            token=token,
            status=status,
            expires_at=expires_at
            or (datetime.now(timezone.utc) + timedelta(days=14)),
            invited_by_user_id=invited_by_user_id,
        )
        db.add(invitation)
        db.commit()
        return invitation.id
    finally:
        db.close()


class TestCreateInvitation:
    def test_admin_creates_invitation_and_calls_email_service(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        admin_id = _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        override_user("hanko-admin")

        response = client.post(
            "/invitations",
            json={
                "organization_id": org_id,
                "email": "Invitee@Example.com",
                "role": "lp",
            },
        )
        assert response.status_code == 201
        body = response.json()
        # Email is normalized to lower-case before persistence.
        assert body["email"] == "invitee@example.com"
        assert body["role"] == "lp"
        assert body["status"] == "pending"
        assert body["organization_id"] == org_id
        assert body["organization"]["id"] == org_id

        # Service called once with the persisted (lower-cased) email and a
        # well-formed accept_url containing the token.
        hanko_email_mock.assert_awaited_once()
        kwargs = hanko_email_mock.await_args.kwargs
        assert kwargs["email"] == "invitee@example.com"
        assert body["token"] in kwargs["accept_url"]
        assert kwargs["organization_name"] == "Eden Capital"

        # Row exists with the inviter recorded.
        db = SessionLocal()
        try:
            row = (
                db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.id == body["id"])
                .one()
            )
            assert row.invited_by_user_id == admin_id
            assert row.status is InvitationStatus.pending
        finally:
            db.close()

    @pytest.mark.parametrize(
        "role,subject",
        [
            (UserRole.fund_manager, "hanko-fm"),
            (UserRole.lp, "hanko-lp"),
        ],
    )
    def test_non_admin_membership_gets_403(
        self, client, override_user, hanko_email_mock, role, subject
    ):
        org_id = _seed_org()
        _seed_user(
            subject, role, email=f"{subject}@example.com", organization_id=org_id
        )
        override_user(subject)

        response = client.post(
            "/invitations",
            json={"organization_id": org_id, "email": "x@example.com", "role": "lp"},
        )
        assert response.status_code == 403
        hanko_email_mock.assert_not_awaited()

    def test_admin_cannot_invite_into_a_different_org(
        self, client, override_user, hanko_email_mock
    ):
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        admin_id = _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_a,
        )
        # The admin _also_ holds a low-priv membership in org_b — this lets
        # ``get_active_membership`` resolve cleanly when X-Organization-Id is
        # passed; the cross-org guard then rejects on
        # ``data.organization_id`` mismatch.
        _seed_membership(admin_id, org_b, UserRole.lp)
        override_user("hanko-admin")

        response = client.post(
            "/invitations",
            json={"organization_id": org_b, "email": "x@example.com", "role": "lp"},
            headers={"X-Organization-Id": str(org_a)},
        )
        assert response.status_code == 403
        hanko_email_mock.assert_not_awaited()

    def test_superadmin_can_invite_into_any_org(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org("Foreign Co")
        _seed_user("hanko-super", UserRole.superadmin, email="root@example.com")
        override_user("hanko-super")

        response = client.post(
            "/invitations",
            json={"organization_id": org_id, "email": "new@example.com", "role": "admin"},
            headers={"X-Organization-Id": str(org_id)},
        )
        assert response.status_code == 201
        hanko_email_mock.assert_awaited_once()

        # Synthesized superadmin membership has no row id, so the invitation
        # records ``invited_by_user_id=None``.
        db = SessionLocal()
        try:
            row = (
                db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.id == response.json()["id"])
                .one()
            )
            assert row.invited_by_user_id is None
        finally:
            db.close()

    def test_superadmin_role_is_rejected_at_schema_layer(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        override_user("hanko-admin")

        response = client.post(
            "/invitations",
            json={
                "organization_id": org_id,
                "email": "x@example.com",
                "role": "superadmin",
            },
        )
        assert response.status_code == 422
        hanko_email_mock.assert_not_awaited()

    def test_404_when_organization_missing(
        self, client, override_user, hanko_email_mock
    ):
        _seed_user("hanko-super", UserRole.superadmin, email="root@example.com")
        override_user("hanko-super")

        response = client.post(
            "/invitations",
            json={"organization_id": 9999, "email": "x@example.com", "role": "lp"},
            headers={"X-Organization-Id": "9999"},
        )
        assert response.status_code == 404
        hanko_email_mock.assert_not_awaited()


class TestListInvitations:
    def test_admin_lists_invitations_for_their_org(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        first = _seed_invitation(org_id, email="a@example.com", token="t-1")
        second = _seed_invitation(org_id, email="b@example.com", token="t-2")
        override_user("hanko-admin")

        response = client.get("/invitations")
        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        # Repository returns desc by id.
        assert ids == [second, first]

    def test_non_admin_gets_403(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp", UserRole.lp, email="lp@example.com", organization_id=org_id
        )
        override_user("hanko-lp")

        response = client.get("/invitations")
        assert response.status_code == 403


class TestRevokeInvitation:
    def test_admin_revokes_pending_invitation(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        invite_id = _seed_invitation(org_id, token="t-revoke")
        override_user("hanko-admin")

        response = client.post(f"/invitations/{invite_id}/revoke")
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"

    def test_revoke_non_pending_returns_409(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        invite_id = _seed_invitation(
            org_id, status=InvitationStatus.accepted, token="t-acc"
        )
        override_user("hanko-admin")

        response = client.post(f"/invitations/{invite_id}/revoke")
        assert response.status_code == 409

    def test_admin_cannot_revoke_another_orgs_invitation(
        self, client, override_user, hanko_email_mock
    ):
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        admin_id = _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_a,
        )
        _seed_membership(admin_id, org_b, UserRole.lp)
        invite_id = _seed_invitation(org_b, token="t-foreign")
        override_user("hanko-admin")

        response = client.post(
            f"/invitations/{invite_id}/revoke",
            headers={"X-Organization-Id": str(org_a)},
        )
        assert response.status_code == 403

    def test_404_when_invitation_missing(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        override_user("hanko-admin")

        response = client.post("/invitations/9999/revoke")
        assert response.status_code == 404


class TestResendInvitation:
    def test_resend_rotates_token_and_sends_email(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        invite_id = _seed_invitation(org_id, token="t-original")
        override_user("hanko-admin")

        response = client.post(f"/invitations/{invite_id}/resend")
        assert response.status_code == 200
        body = response.json()
        # Token must rotate so the prior email's link stops working.
        assert body["token"] != "t-original"
        assert body["status"] == "pending"
        hanko_email_mock.assert_awaited_once()
        kwargs = hanko_email_mock.await_args.kwargs
        assert body["token"] in kwargs["accept_url"]

    def test_resend_non_pending_returns_409(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        invite_id = _seed_invitation(
            org_id, status=InvitationStatus.revoked, token="t-rev"
        )
        override_user("hanko-admin")

        response = client.post(f"/invitations/{invite_id}/resend")
        assert response.status_code == 409
        hanko_email_mock.assert_not_awaited()


class TestAcceptInvitation:
    def test_signed_in_invitee_accepts_creates_membership(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        invitee_id = _seed_user(
            "hanko-invitee",
            UserRole.lp,
            email="invitee@example.com",
        )
        invite_id = _seed_invitation(
            org_id,
            email="invitee@example.com",
            role=UserRole.fund_manager,
            token="t-accept",
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "t-accept"})
        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == invitee_id
        assert body["organization_id"] == org_id
        assert body["role"] == "fund_manager"

        db = SessionLocal()
        try:
            invitation = (
                db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.id == invite_id)
                .one()
            )
            assert invitation.status is InvitationStatus.accepted
            assert invitation.accepted_at is not None
        finally:
            db.close()

    def test_second_accept_attempt_returns_410(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-invitee", UserRole.lp, email="invitee@example.com"
        )
        _seed_invitation(
            org_id, email="invitee@example.com", token="t-twice"
        )
        override_user("hanko-invitee", email="invitee@example.com")

        first = client.post("/invitations/accept", json={"token": "t-twice"})
        assert first.status_code == 200
        second = client.post("/invitations/accept", json={"token": "t-twice"})
        assert second.status_code == 410

    def test_accept_with_email_mismatch_returns_403(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user("hanko-other", UserRole.lp, email="other@example.com")
        _seed_invitation(
            org_id, email="invitee@example.com", token="t-mismatch"
        )
        override_user("hanko-other", email="other@example.com")

        response = client.post(
            "/invitations/accept", json={"token": "t-mismatch"}
        )
        assert response.status_code == 403

    def test_accept_revoked_returns_410(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-invitee", UserRole.lp, email="invitee@example.com"
        )
        _seed_invitation(
            org_id,
            email="invitee@example.com",
            status=InvitationStatus.revoked,
            token="t-revoked",
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post(
            "/invitations/accept", json={"token": "t-revoked"}
        )
        assert response.status_code == 410

    def test_accept_expired_flips_status_and_returns_410(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-invitee", UserRole.lp, email="invitee@example.com"
        )
        invite_id = _seed_invitation(
            org_id,
            email="invitee@example.com",
            token="t-stale",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post(
            "/invitations/accept", json={"token": "t-stale"}
        )
        assert response.status_code == 410

        db = SessionLocal()
        try:
            invitation = (
                db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.id == invite_id)
                .one()
            )
            assert invitation.status is InvitationStatus.expired
        finally:
            db.close()

    def test_accept_unknown_token_returns_404(
        self, client, override_user, hanko_email_mock
    ):
        _seed_user(
            "hanko-invitee", UserRole.lp, email="invitee@example.com"
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post(
            "/invitations/accept", json={"token": "no-such-token"}
        )
        assert response.status_code == 404

    def test_accept_upgrades_existing_membership_role(
        self, client, override_user, hanko_email_mock
    ):
        """An already-member who re-accepts at a higher role gets upgraded
        rather than duplicated. Mirrors the seeded-lp re-invite flow."""
        org_id = _seed_org()
        invitee_id = _seed_user(
            "hanko-invitee",
            UserRole.lp,
            email="invitee@example.com",
            organization_id=org_id,
        )
        # ``_seed_user`` with ``organization_id`` already created an lp
        # membership; the invite re-grants admin.
        _seed_invitation(
            org_id,
            email="invitee@example.com",
            role=UserRole.admin,
            token="t-upgrade",
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post(
            "/invitations/accept", json={"token": "t-upgrade"}
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

        db = SessionLocal()
        try:
            memberships = (
                db.query(UserOrganizationMembership)
                .filter(
                    UserOrganizationMembership.user_id == invitee_id,
                    UserOrganizationMembership.organization_id == org_id,
                )
                .all()
            )
            # No duplicate row was created.
            assert len(memberships) == 1
            assert memberships[0].role is UserRole.admin
        finally:
            db.close()


class TestPendingForMe:
    def test_lists_invitations_matching_jwt_email_case_insensitive(
        self, client, override_user, hanko_email_mock
    ):
        org_a = _seed_org("Org A")
        org_b = _seed_org("Org B")
        _seed_user("hanko-me", UserRole.lp, email="me@example.com")
        target_id = _seed_invitation(org_a, email="me@example.com", token="t-a")
        other_org_id = _seed_invitation(org_b, email="me@example.com", token="t-b")
        # Different email — must not appear.
        _seed_invitation(org_a, email="someone@example.com", token="t-other")
        # Same email but already accepted — must not appear.
        _seed_invitation(
            org_a,
            email="me@example.com",
            status=InvitationStatus.accepted,
            token="t-done",
        )
        override_user("hanko-me", email="ME@example.com")

        response = client.get("/invitations/pending-for-me")
        assert response.status_code == 200
        ids = {row["id"] for row in response.json()}
        assert ids == {target_id, other_org_id}

    def test_returns_empty_when_no_email_claim(
        self, client, override_user, hanko_email_mock
    ):
        # No email seeded on the user row either.
        db = SessionLocal()
        try:
            user = User(
                role=UserRole.lp,
                first_name="No",
                last_name="Email",
                email="",
                hanko_subject_id="hanko-blank",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()
        override_user("hanko-blank")

        response = client.get("/invitations/pending-for-me")
        assert response.status_code == 200
        assert response.json() == []
