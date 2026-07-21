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

The Hanko service is patched at ``app.routers.invitations.ensure_hanko_user``
so no HTTP traffic leaves the test process. The invitation email itself is
delivered by the arq worker (``task_send_invitation_email``) — the router only
enqueues, and ``enqueue_or_log`` swallows Redis failures, so these tests pass
with or without a reachable Redis.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import (
    Investor,
    InvestorContact,
    Organization,
    OrganizationInvitation,
    OrganizationType,
    User,
    UserOrganizationMembership,
    UserRole,
)
from app.models.enums import InvitationStatus
from app.models.notification import Notification


@pytest.fixture(autouse=True)
def configure_superadmin(monkeypatch):
    """Superadmins are config-defined; register the email these tests
    sign superadmins in with."""
    monkeypatch.setattr(settings, "SUPERADMIN_EMAIL", "root@example.com")


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def hanko_email_mock():
    """Patch the router-level ``ensure_hanko_user`` reference.

    The router imports the function with ``from app.services.hanko import
    ensure_hanko_user``, so we patch the binding in the router module.
    Returns ``True`` by default — individual tests can override the
    return value by setting ``mock.return_value`` (after re-wrapping with
    ``AsyncMock`` if they need an async side effect).
    """
    with patch(
        "app.routers.invitations.ensure_hanko_user",
        new=AsyncMock(return_value=True),
    ) as mock:
        yield mock


def _seed_org(name: str = "NewTaven Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(
            name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm
        )
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
            expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(days=14)),
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
                "organization_id": str(org_id),
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
        assert body["organization_id"] == str(org_id)
        assert body["organization"]["id"] == str(org_id)

        # Hanko pre-provisioning called once with the persisted
        # (lower-cased) email; the email itself is sent by the worker task.
        hanko_email_mock.assert_awaited_once_with("invitee@example.com")

        # Row exists with the inviter recorded.
        db = SessionLocal()
        try:
            row = (
                db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.id == uuid.UUID(body["id"]))
                .one()
            )
            assert row.invited_by_user_id == admin_id
            assert row.status is InvitationStatus.pending
        finally:
            db.close()

    def test_lp_membership_cannot_invite(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp", UserRole.lp, email="lp@example.com", organization_id=org_id
        )
        override_user("hanko-lp")

        response = client.post(
            "/invitations",
            json={
                "organization_id": str(org_id),
                "email": "x@example.com",
                "role": "lp",
            },
        )
        assert response.status_code == 403
        hanko_email_mock.assert_not_awaited()

    def test_fund_manager_can_invite_lp(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.post(
            "/invitations",
            json={
                "organization_id": str(org_id),
                "email": "newlp@example.com",
                "role": "lp",
            },
        )
        assert response.status_code == 201
        assert response.json()["role"] == "lp"
        hanko_email_mock.assert_awaited_once_with("newlp@example.com")

    @pytest.mark.parametrize("role", ["fund_manager", "admin"])
    def test_fund_manager_cannot_invite_managers(
        self, client, override_user, hanko_email_mock, role
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")

        response = client.post(
            "/invitations",
            json={
                "organization_id": str(org_id),
                "email": "staff@example.com",
                "role": role,
            },
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
            json={
                "organization_id": str(org_b),
                "email": "x@example.com",
                "role": "lp",
            },
            headers={"X-Organization-Id": str(org_a)},
        )
        assert response.status_code == 403
        hanko_email_mock.assert_not_awaited()

    def test_superadmin_cannot_invite_and_must_use_superadmin_routes(
        self, client, override_user, hanko_email_mock
    ):
        """Superadmin tenant impersonation was removed (commit 735395bc): the
        whole ``/invitations`` router sits behind
        ``Depends(require_tenant_user)`` (app/core/rbac.py), which
        unconditionally 403s ``current_user.is_superadmin`` before any route
        body runs. Superadmins grant org access via
        ``app/routers/superadmin.py::assign_organization_admin`` instead —
        there is no superadmin invitation route at all
        (``grep -n "invit" app/routers/superadmin.py`` returns nothing). This
        test pins that access-control boundary rather than a since-removed
        capability."""
        org_id = _seed_org("Foreign Co")
        _seed_user("hanko-super", UserRole.superadmin, email="root@example.com")
        override_user("hanko-super")

        response = client.post(
            "/invitations",
            json={
                "organization_id": str(org_id),
                "email": "new@example.com",
                "role": "admin",
            },
            headers={"X-Organization-Id": str(org_id)},
        )
        assert response.status_code == 403
        hanko_email_mock.assert_not_awaited()

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
                "organization_id": str(org_id),
                "email": "x@example.com",
                "role": "superadmin",
            },
        )
        assert response.status_code == 422
        hanko_email_mock.assert_not_awaited()

    # test_404_when_organization_missing was removed rather than re-seated on
    # a tenant admin: the "organization not found" branch in
    # create_invitation (app/routers/invitations.py) is unreachable for any
    # non-superadmin caller. require_membership_roles resolves the caller's
    # active UserOrganizationMembership, whose organization_id is a NOT NULL
    # foreign key to organizations.id (app/models/user_organization_membership.py)
    # — a membership can only ever point at a row that exists (orgs are only
    # ever soft-disabled via superadmin's disable/enable routes, never
    # deleted). _ensure_can_act_on_org then 403s unless
    # data.organization_id == membership.organization_id, so a tenant admin
    # can never submit an organization_id other than their own, already-
    # verified-to-exist org. The only caller that could previously reach a
    # missing-org 404 was a superadmin supplying an arbitrary
    # X-Organization-Id, and that path is now blocked upstream by
    # require_tenant_user (see the test above) before this branch is ever
    # reached — so keeping a test for it would pass for the wrong reason.


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
        # Ordering is (created_at, id) desc and covered by the repository
        # tests — here just assert the org's rows are all present.
        assert set(ids) == {str(first), str(second)}

    def test_non_admin_gets_403(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        _seed_user(
            "hanko-lp", UserRole.lp, email="lp@example.com", organization_id=org_id
        )
        override_user("hanko-lp")

        response = client.get("/invitations")
        assert response.status_code == 403

    def test_fund_manager_sees_only_lp_invitations(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        _seed_invitation(org_id, email="lp@example.com", role=UserRole.lp, token="t-lp")
        _seed_invitation(
            org_id,
            email="mgr@example.com",
            role=UserRole.fund_manager,
            token="t-mgr",
        )
        override_user("hanko-fm")

        response = client.get("/invitations")
        assert response.status_code == 200
        roles = {row["role"] for row in response.json()}
        assert roles == {"lp"}


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

    def test_fund_manager_revokes_lp_invitation(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        invite_id = _seed_invitation(org_id, role=UserRole.lp, token="t-fm-revoke")
        override_user("hanko-fm")

        response = client.post(f"/invitations/{invite_id}/revoke")
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"

    def test_fund_manager_cannot_revoke_manager_invitation(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        invite_id = _seed_invitation(
            org_id, role=UserRole.fund_manager, token="t-fm-noaccess"
        )
        override_user("hanko-fm")

        response = client.post(f"/invitations/{invite_id}/revoke")
        assert response.status_code == 403

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

    def test_404_when_invitation_missing(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        override_user("hanko-admin")

        response = client.post(f"/invitations/{uuid.uuid4()}/revoke")
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
        # Hanko pre-provisioning re-runs on resend; the rotated-token email
        # is delivered by the worker task.
        hanko_email_mock.assert_awaited_once_with("invitee@example.com")

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
        assert body["organization_id"] == str(org_id)
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
            membership = (
                db.query(UserOrganizationMembership)
                .filter(
                    UserOrganizationMembership.user_id == invitee_id,
                    UserOrganizationMembership.organization_id == org_id,
                )
                .one()
            )
            assert membership.role is UserRole.fund_manager
        finally:
            db.close()

    def test_accept_notifies_the_inviter(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        inviter_id = _seed_user(
            "hanko-admin",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        _seed_user("hanko-invitee", UserRole.lp, email="invitee@example.com")
        invite_id = _seed_invitation(
            org_id,
            email="invitee@example.com",
            token="t-notify",
            invited_by_user_id=inviter_id,
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "t-notify"})
        assert response.status_code == 200

        db = SessionLocal()
        try:
            rows = (
                db.query(Notification).filter(Notification.user_id == inviter_id).all()
            )
            assert len(rows) == 1
            assert rows[0].title == "Invitation accepted"
            assert "invitee@example.com" in rows[0].message
            assert rows[0].related_type == "invitation"
            assert rows[0].related_id == invite_id
        finally:
            db.close()

    def test_accept_without_recorded_inviter_creates_no_notification(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user("hanko-invitee", UserRole.lp, email="invitee@example.com")
        _seed_invitation(
            org_id,
            email="invitee@example.com",
            token="t-no-inviter",
            invited_by_user_id=None,
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "t-no-inviter"})
        assert response.status_code == 200

        db = SessionLocal()
        try:
            assert db.query(Notification).count() == 0
        finally:
            db.close()

    def test_second_accept_attempt_returns_410(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user("hanko-invitee", UserRole.lp, email="invitee@example.com")
        _seed_invitation(org_id, email="invitee@example.com", token="t-twice")
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
        _seed_invitation(org_id, email="invitee@example.com", token="t-mismatch")
        override_user("hanko-other", email="other@example.com")

        response = client.post("/invitations/accept", json={"token": "t-mismatch"})
        assert response.status_code == 403

    def test_accept_revoked_returns_410(self, client, override_user, hanko_email_mock):
        org_id = _seed_org()
        _seed_user("hanko-invitee", UserRole.lp, email="invitee@example.com")
        _seed_invitation(
            org_id,
            email="invitee@example.com",
            status=InvitationStatus.revoked,
            token="t-revoked",
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "t-revoked"})
        assert response.status_code == 410

    def test_accept_expired_flips_status_and_returns_410(
        self, client, override_user, hanko_email_mock
    ):
        org_id = _seed_org()
        _seed_user("hanko-invitee", UserRole.lp, email="invitee@example.com")
        invite_id = _seed_invitation(
            org_id,
            email="invitee@example.com",
            token="t-stale",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "t-stale"})
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
        _seed_user("hanko-invitee", UserRole.lp, email="invitee@example.com")
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "no-such-token"})
        assert response.status_code == 404

    def test_accept_lp_invitation_creates_no_membership_and_links_contacts(
        self, client, override_user, hanko_email_mock
    ):
        """Investor invitations grant portal access purely via contact links —
        accepting one must not create a membership row."""
        org_id = _seed_org()
        db = SessionLocal()
        try:
            investor = Investor(organization_id=org_id, name="Acme LP")
            db.add(investor)
            db.flush()
            contact = InvestorContact(
                investor_id=investor.id,
                first_name="Pat",
                last_name="Lp",
                email="invitee@example.com",
            )
            db.add(contact)
            db.commit()
            contact_id = contact.id
        finally:
            db.close()

        invitee_id = _seed_user(
            "hanko-invitee", UserRole.lp, email="invitee@example.com"
        )
        _seed_invitation(
            org_id, email="invitee@example.com", role=UserRole.lp, token="t-lp"
        )
        override_user("hanko-invitee", email="invitee@example.com")

        response = client.post("/invitations/accept", json={"token": "t-lp"})
        assert response.status_code == 200
        body = response.json()
        assert body["organization_id"] == str(org_id)
        assert body["role"] == "lp"
        assert body["organization"]["id"] == str(org_id)

        db = SessionLocal()
        try:
            memberships = (
                db.query(UserOrganizationMembership)
                .filter(UserOrganizationMembership.user_id == invitee_id)
                .all()
            )
            assert memberships == []
            linked = (
                db.query(InvestorContact).filter(InvestorContact.id == contact_id).one()
            )
            assert linked.user_id == invitee_id
        finally:
            db.close()

    def test_accept_lp_invitation_preserves_staff_role(
        self, client, override_user, hanko_email_mock
    ):
        """An admin who is personally an investor accepts an lp invitation:
        their contact gets linked and their admin membership is untouched."""
        org_id = _seed_org()
        invitee_id = _seed_user(
            "hanko-admin-investor",
            UserRole.admin,
            email="admin@example.com",
            organization_id=org_id,
        )
        db = SessionLocal()
        try:
            investor = Investor(organization_id=org_id, name="Admin Family LP")
            db.add(investor)
            db.flush()
            db.add(
                InvestorContact(
                    investor_id=investor.id,
                    first_name="Ada",
                    last_name="Admin",
                    email="admin@example.com",
                )
            )
            db.commit()
        finally:
            db.close()
        _seed_invitation(
            org_id, email="admin@example.com", role=UserRole.lp, token="t-adm-lp"
        )
        override_user("hanko-admin-investor", email="admin@example.com")

        response = client.post("/invitations/accept", json={"token": "t-adm-lp"})
        assert response.status_code == 200

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
            assert len(memberships) == 1
            # The staff role survives — no downgrade to lp.
            assert memberships[0].role is UserRole.admin
        finally:
            db.close()

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

        response = client.post("/invitations/accept", json={"token": "t-upgrade"})
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
        assert ids == {str(target_id), str(other_org_id)}

    def test_returns_empty_when_no_email_claim(
        self, client, override_user, hanko_email_mock
    ):
        # No email seeded on the user row either.
        db = SessionLocal()
        try:
            user = User(
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
