"""Integration tests for the audit-log machinery.

Covers the SQLAlchemy event listeners (auto-emitted on insert/update/delete
of audited models), the ``record_audit`` helper, and the admin-only
``GET /audit-logs`` route.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.audit import record_audit
from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.middleware.audit_context import (
    AuditContext,
    get_audit_context,
    set_audit_context,
)
from app.models import (
    AuditLog,
    Fund,
    Organization,
    OrganizationType,
    User,
    UserRole,
)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_audit_context():
    """Force a fresh ``AuditContext`` per test so seed data isn't attributed."""
    set_audit_context()
    yield
    set_audit_context()


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


def _audit_rows(
    *, entity_type: str | None = None, action: str | None = None
) -> list[AuditLog]:
    db = SessionLocal()
    try:
        query = db.query(AuditLog)
        if entity_type is not None:
            query = query.filter(AuditLog.entity_type == entity_type)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        return query.order_by(AuditLog.id).all()
    finally:
        db.close()


class TestEventListeners:
    def test_insert_emits_create_row(self):
        org_id = _seed_org("Listener Co")
        rows = _audit_rows(entity_type="organization", action="create")
        assert len(rows) == 1
        assert rows[0].entity_id == org_id
        assert rows[0].action == "create"

    def test_update_emits_diff(self):
        org_id = _seed_org("Original")
        # Clear the create row so we only assert the update behaviour.
        db = SessionLocal()
        try:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            assert org is not None
            org.name = "Renamed"
            db.commit()
        finally:
            db.close()

        update_rows = _audit_rows(entity_type="organization", action="update")
        assert len(update_rows) == 1
        payload = json.loads(update_rows[0].audit_metadata)
        assert "changes" in payload
        assert payload["changes"]["name"] == {
            "before": "Original",
            "after": "Renamed",
        }

    def test_no_op_update_does_not_emit(self):
        org_id = _seed_org("Stable")
        db = SessionLocal()
        try:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            assert org is not None
            # Re-assigning the same value still bumps `updated_at` via onupdate
            # but should not emit an audit row because the diff is empty.
            org.name = "Stable"
            db.commit()
        finally:
            db.close()
        assert _audit_rows(entity_type="organization", action="update") == []

    def test_delete_emits_delete_row(self):
        org_id = _seed_org()
        fund_id_holder: dict[str, int] = {}
        db = SessionLocal()
        try:
            fund = Fund(organization_id=org_id, name="Doomed Fund")
            db.add(fund)
            db.commit()
            fund_id_holder["id"] = fund.id
            db.delete(fund)
            db.commit()
        finally:
            db.close()
        delete_rows = _audit_rows(entity_type="fund", action="delete")
        assert len(delete_rows) == 1
        assert delete_rows[0].entity_id == fund_id_holder["id"]

    def test_actor_is_pulled_from_context(self):
        org_id = _seed_org()
        user_id = _seed_user("hanko-actor", UserRole.admin, organization_id=org_id)
        # Simulate request scope after auth
        set_audit_context(user_id=user_id, ip_address="10.0.0.1")
        db = SessionLocal()
        try:
            fund = Fund(organization_id=org_id, name="Audited Fund")
            db.add(fund)
            db.commit()
        finally:
            db.close()
        rows = _audit_rows(entity_type="fund", action="create")
        assert len(rows) == 1
        assert rows[0].user_id == user_id
        assert rows[0].ip_address == "10.0.0.1"
        assert rows[0].organization_id == org_id


class TestRecordAuditHelper:
    def test_writes_row_with_metadata(self):
        org_id = _seed_org()
        user_id = _seed_user("hanko-actor", UserRole.admin, organization_id=org_id)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            assert user is not None
            log = record_audit(
                db,
                user=user,
                action="login",
                entity_type="session",
                entity_id=None,
                metadata={"reason": "manual"},
            )
            assert log.id is not None
            assert log.action == "login"
            assert json.loads(log.audit_metadata) == {"reason": "manual"}
            assert log.user_id == user_id
        finally:
            db.close()


class TestAuditLogRoute:
    def test_admin_can_list(self, client, override_user):
        admin_id = _seed_user("hanko-admin", UserRole.admin)
        # Trigger one audited write.
        _seed_org("Visible Org")
        override_user("hanko-admin")
        resp = client.get("/audit-logs")
        assert resp.status_code == 200
        rows = resp.json()
        assert any(r["entity_type"] == "organization" for r in rows)
        assert all("user_id" in r for r in rows)
        assert admin_id is not None

    def test_filter_by_entity(self, client, override_user):
        _seed_user("hanko-admin", UserRole.admin)
        org_id = _seed_org("Eden")
        db = SessionLocal()
        try:
            fund = Fund(organization_id=org_id, name="Filter Fund")
            db.add(fund)
            db.commit()
            fund_id = fund.id
        finally:
            db.close()
        override_user("hanko-admin")
        resp = client.get(
            f"/audit-logs?entity_type=fund&entity_id={fund_id}"
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert rows
        for row in rows:
            assert row["entity_type"] == "fund"
            assert row["entity_id"] == fund_id

    def test_non_admin_forbidden(self, client, override_user):
        _seed_user("hanko-fm", UserRole.fund_manager)
        override_user("hanko-fm")
        resp = client.get("/audit-logs")
        assert resp.status_code == 403

    def test_lp_forbidden(self, client, override_user):
        _seed_user("hanko-lp", UserRole.lp)
        override_user("hanko-lp")
        resp = client.get("/audit-logs")
        assert resp.status_code == 403


def test_audit_context_default_is_empty():
    set_audit_context()
    ctx = get_audit_context()
    assert isinstance(ctx, AuditContext)
    assert ctx.user_id is None
    assert ctx.ip_address is None
