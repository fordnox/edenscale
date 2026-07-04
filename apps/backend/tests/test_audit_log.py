"""Integration tests for the audit-log machinery.

Covers the SQLAlchemy event listeners (auto-emitted on insert/update/delete
of audited models), the ``record_audit`` helper, and the membership-scoped
``GET /audit-logs`` route (org-visible roles see the org's events, everyone
else only their own).
"""

import json
from app.core.slugs import slugify

import pytest
from fastapi.testclient import TestClient

from app.core.audit import _ENTITY_TYPES, _UNAUDITED_MODELS, record_audit
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.middleware.audit_context import (
    AuditContext,
    get_audit_context,
    set_audit_context,
)
from app.models import (
    AuditLog,
    CapitalCall,
    CapitalCallItem,
    Commitment,
    Fund,
    Investor,
    InvestorContact,
    Organization,
    OrganizationType,
    User,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership


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


def _seed_org(name: str = "NewTaven Capital") -> int:
    db = SessionLocal()
    try:
        org = Organization(name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm)
        db.add(org)
        db.commit()
        return str(org.id)
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
        return str(user.id)
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
        assert str(rows[0].entity_id) == org_id
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
            fund = Fund(organization_id=org_id, name="Doomed Fund", slug=slugify("Doomed Fund"))
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
            fund = Fund(organization_id=org_id, name="Audited Fund", slug=slugify("Audited Fund"))
            db.add(fund)
            db.commit()
        finally:
            db.close()
        rows = _audit_rows(entity_type="fund", action="create")
        assert len(rows) == 1
        assert str(rows[0].user_id) == user_id
        assert rows[0].ip_address == "10.0.0.1"
        assert str(rows[0].organization_id) == org_id


class TestListenerCoverage:
    def test_every_mapped_model_is_classified(self):
        """Every ORM model must be audited or explicitly excluded — adding a
        model without classifying it in ``app.core.audit`` fails here."""
        mapped = {mapper.class_ for mapper in Base.registry.mappers}
        classified = set(_ENTITY_TYPES) | _UNAUDITED_MODELS
        assert mapped == classified, (
            f"unclassified models: {mapped - classified}; "
            f"stale entries: {classified - mapped}"
        )

    def test_investor_create_is_audited_with_direct_org(self):
        org_id = _seed_org()
        db = SessionLocal()
        try:
            investor = Investor(organization_id=org_id, name="Northstar Trust")
            db.add(investor)
            db.commit()
            investor_id = str(investor.id)
        finally:
            db.close()

        rows = _audit_rows(entity_type="investor", action="create")
        assert len(rows) == 1
        assert str(rows[0].entity_id) == investor_id
        assert str(rows[0].organization_id) == org_id

    def test_investor_contact_resolves_org_through_investor(self):
        org_id = _seed_org()
        db = SessionLocal()
        try:
            investor = Investor(organization_id=org_id, name="Atlas Family Office")
            db.add(investor)
            db.flush()
            contact = InvestorContact(
                investor_id=investor.id, first_name="Elena", last_name="Park"
            )
            db.add(contact)
            db.commit()
        finally:
            db.close()

        rows = _audit_rows(entity_type="investor_contact", action="create")
        assert len(rows) == 1
        assert str(rows[0].organization_id) == org_id

    def test_capital_call_item_resolves_org_through_call_and_fund(self):
        from datetime import date

        org_id = _seed_org()
        db = SessionLocal()
        try:
            fund = Fund(
                organization_id=org_id, name="Fund I", slug=slugify("Fund I")
            )
            investor = Investor(organization_id=org_id, name="LP One")
            db.add_all([fund, investor])
            db.flush()
            commitment = Commitment(
                fund_id=fund.id,
                investor_id=investor.id,
                committed_amount=1_000_000,
                commitment_date=date(2026, 1, 1),
            )
            db.add(commitment)
            db.flush()
            call = CapitalCall(
                fund_id=fund.id,
                title="Call 1",
                due_date=date(2026, 8, 1),
                amount=100_000,
            )
            db.add(call)
            db.flush()
            item = CapitalCallItem(
                capital_call_id=call.id,
                commitment_id=commitment.id,
                amount_due=100_000,
            )
            db.add(item)
            db.commit()
        finally:
            db.close()

        rows = _audit_rows(entity_type="capital_call_item", action="create")
        assert len(rows) == 1
        assert str(rows[0].organization_id) == org_id


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
            assert str(log.user_id) == user_id
        finally:
            db.close()


class TestAuditLogRoute:
    def test_admin_can_list(self, client, override_user):
        # Trigger one audited write.
        org_id = _seed_org("Visible Org")
        admin_id = _seed_user("hanko-admin", UserRole.admin, organization_id=org_id)
        override_user("hanko-admin")
        resp = client.get("/audit-logs")
        assert resp.status_code == 200
        rows = resp.json()
        assert any(r["entity_type"] == "organization" for r in rows)
        assert all("user_id" in r for r in rows)
        assert admin_id is not None

    def test_filter_by_entity(self, client, override_user):
        org_id = _seed_org("NewTaven")
        _seed_user("hanko-admin", UserRole.admin, organization_id=org_id)
        db = SessionLocal()
        try:
            fund = Fund(organization_id=org_id, name="Filter Fund", slug=slugify("Filter Fund"))
            db.add(fund)
            db.commit()
            fund_id = str(fund.id)
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

    def test_filter_by_date_range(self, client, override_user):
        from datetime import datetime, timedelta, timezone

        # Two audited writes in the same org; backdate the first one so the
        # date filter excludes it.
        org_id = _seed_org("Old Org")
        _seed_user("hanko-admin", UserRole.admin, organization_id=org_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db = SessionLocal()
        try:
            fund = Fund(
                organization_id=org_id,
                name="Recent Fund",
                slug=slugify("Recent Fund"),
            )
            db.add(fund)
            db.commit()
            old_row = (
                db.query(AuditLog)
                .filter(AuditLog.entity_type == "organization")
                .filter(AuditLog.entity_id == org_id)
                .order_by(AuditLog.id)
                .first()
            )
            assert old_row is not None
            old_row.created_at = now - timedelta(days=10)
            db.add(old_row)
            db.commit()
            old_row_id = str(old_row.id)
        finally:
            db.close()

        cutoff = (now - timedelta(days=1)).isoformat()
        override_user("hanko-admin")
        resp = client.get(f"/audit-logs?date_from={cutoff}")
        assert resp.status_code == 200
        rows = resp.json()
        assert rows
        assert all(row["id"] != old_row_id for row in rows)

        # date_to set to the past should return only the older row(s).
        upper = (now - timedelta(days=2)).isoformat()
        resp = client.get(f"/audit-logs?date_to={upper}")
        assert resp.status_code == 200
        rows = resp.json()
        assert any(row["id"] == old_row_id for row in rows)

    def test_fund_manager_can_list_org_events(self, client, override_user):
        org_id = _seed_org("FM Org")
        _seed_user("hanko-fm", UserRole.fund_manager, organization_id=org_id)
        override_user("hanko-fm")
        resp = client.get("/audit-logs")
        assert resp.status_code == 200
        assert any(r["entity_type"] == "organization" for r in resp.json())

    def test_lp_sees_only_own_events(self, client, override_user):
        org_id = _seed_org("LP Org")
        _seed_user("hanko-lp", UserRole.lp, organization_id=org_id)
        override_user("hanko-lp")
        resp = client.get("/audit-logs")
        assert resp.status_code == 200
        # The seeded writes weren't caused by the LP, so nothing is visible.
        assert resp.json() == []


def test_audit_context_default_is_empty():
    set_audit_context()
    ctx = get_audit_context()
    assert isinstance(ctx, AuditContext)
    assert ctx.user_id is None
    assert ctx.ip_address is None
