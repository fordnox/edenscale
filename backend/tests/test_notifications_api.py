"""Integration tests for the /notifications router and the
notification fan-out from capital-call/distribution/communication/task flows."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Commitment,
    CommitmentStatus,
    Fund,
    Investor,
    InvestorContact,
    Notification,
    NotificationStatus,
    Organization,
    OrganizationType,
    Task,
    User,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership


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


def _seed_fund(organization_id: int, *, name: str = "Eden Fund I") -> int:
    db = SessionLocal()
    try:
        fund = Fund(organization_id=organization_id, name=name)
        db.add(fund)
        db.commit()
        return fund.id
    finally:
        db.close()


def _seed_investor(organization_id: int, *, name: str = "Acme LP") -> int:
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name=name)
        db.add(investor)
        db.commit()
        return investor.id
    finally:
        db.close()


def _seed_commitment(
    fund_id: int,
    investor_id: int,
    *,
    committed_amount: Decimal = Decimal("1000.00"),
    status: CommitmentStatus = CommitmentStatus.approved,
) -> int:
    db = SessionLocal()
    try:
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=committed_amount,
            commitment_date=date(2026, 1, 1),
            status=status,
        )
        db.add(commitment)
        db.commit()
        return commitment.id
    finally:
        db.close()


def _seed_contact(
    investor_id: int,
    user_id: int | None,
    *,
    is_primary: bool = True,
) -> int:
    db = SessionLocal()
    try:
        contact = InvestorContact(
            investor_id=investor_id,
            user_id=user_id,
            first_name="Lp",
            last_name="Contact",
            is_primary=is_primary,
        )
        db.add(contact)
        db.commit()
        return contact.id
    finally:
        db.close()


def _seed_notification(
    user_id: int,
    *,
    title: str = "Hello",
    message: str = "World",
    status: NotificationStatus = NotificationStatus.unread,
    related_type: str | None = None,
    related_id: int | None = None,
) -> int:
    db = SessionLocal()
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            status=status,
            related_type=related_type,
            related_id=related_id,
        )
        db.add(notification)
        db.commit()
        return notification.id
    finally:
        db.close()


def _list_notifications(user_id: int) -> list[Notification]:
    db = SessionLocal()
    try:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.id)
            .all()
        )
    finally:
        db.close()


class TestNotificationListing:
    def test_lists_only_current_users_notifications_desc(self, client, override_user):
        user_id = _seed_user("hanko-me", UserRole.lp)
        other_id = _seed_user("hanko-other", UserRole.lp, email="other@example.com")
        # Older then newer for the current user
        _seed_notification(user_id, title="Older")
        _seed_notification(user_id, title="Newer")
        # Should not appear: another user's notification
        _seed_notification(other_id, title="Theirs")

        override_user("hanko-me")
        resp = client.get("/notifications")
        assert resp.status_code == 200
        rows = resp.json()
        titles = [row["title"] for row in rows]
        assert titles[0] == "Newer"
        assert "Older" in titles
        assert "Theirs" not in titles

    def test_status_filter_returns_only_matching(self, client, override_user):
        user_id = _seed_user("hanko-me", UserRole.lp)
        _seed_notification(user_id, title="Unread one")
        _seed_notification(user_id, title="Read one", status=NotificationStatus.read)

        override_user("hanko-me")
        resp = client.get("/notifications?status_filter=unread")
        assert resp.status_code == 200
        titles = [row["title"] for row in resp.json()]
        assert titles == ["Unread one"]


class TestNotificationActions:
    def test_mark_read(self, client, override_user):
        user_id = _seed_user("hanko-me", UserRole.lp)
        notif_id = _seed_notification(user_id)

        override_user("hanko-me")
        resp = client.post(f"/notifications/{notif_id}/read")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "read"
        assert body["read_at"] is not None

    def test_archive(self, client, override_user):
        user_id = _seed_user("hanko-me", UserRole.lp)
        notif_id = _seed_notification(user_id)

        override_user("hanko-me")
        resp = client.post(f"/notifications/{notif_id}/archive")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_read_all_marks_unread_only(self, client, override_user):
        user_id = _seed_user("hanko-me", UserRole.lp)
        _seed_notification(user_id, title="One")
        _seed_notification(user_id, title="Two")
        _seed_notification(
            user_id, title="Already read", status=NotificationStatus.read
        )
        _seed_notification(
            user_id, title="Archived", status=NotificationStatus.archived
        )

        override_user("hanko-me")
        resp = client.post("/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["updated"] == 2
        statuses = [n.status for n in _list_notifications(user_id)]
        assert statuses.count(NotificationStatus.read) == 3
        assert statuses.count(NotificationStatus.archived) == 1

    def test_cannot_mark_other_users_notification(self, client, override_user):
        user_id = _seed_user("hanko-me", UserRole.lp)
        other_id = _seed_user("hanko-other", UserRole.lp, email="other@example.com")
        notif_id = _seed_notification(other_id)
        assert user_id != other_id

        override_user("hanko-me")
        resp = client.post(f"/notifications/{notif_id}/read")
        assert resp.status_code == 403

    def test_mark_unknown_returns_404(self, client, override_user):
        _seed_user("hanko-me", UserRole.lp)
        override_user("hanko-me")
        resp = client.post("/notifications/9999/read")
        assert resp.status_code == 404


class TestNotificationFanOut:
    def test_communication_send_creates_notifications(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id, name="Approved LP")
        _seed_commitment(fund_id, investor_id, status=CommitmentStatus.approved)
        lp_user_id = _seed_user(
            "hanko-lp",
            UserRole.lp,
            email="lp@example.com",
            organization_id=org_id,
        )
        _seed_contact(investor_id, lp_user_id, is_primary=True)

        create_resp = client.post(
            "/communications",
            json={
                "fund_id": fund_id,
                "type": "announcement",
                "subject": "Q1 Update",
                "body": "Hello LPs",
            },
        )
        comm_id = create_resp.json()["id"]
        send_resp = client.post(f"/communications/{comm_id}/send")
        assert send_resp.status_code == 200

        rows = _list_notifications(lp_user_id)
        assert len(rows) == 1
        assert rows[0].related_type == "communication"
        assert rows[0].related_id == comm_id
        assert "Q1 Update" in rows[0].title

    def test_task_assignment_notifies_assignee(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        assignee_id = _seed_user(
            "hanko-assignee",
            UserRole.lp,
            email="assignee@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        resp = client.post(
            "/tasks",
            json={
                "fund_id": fund_id,
                "title": "Sign docs",
                "assigned_to_user_id": assignee_id,
            },
        )
        assert resp.status_code == 201
        rows = _list_notifications(assignee_id)
        assert len(rows) == 1
        assert rows[0].related_type == "task"
        assert "Sign docs" in rows[0].title

    def test_task_self_assignment_does_not_notify(self, client, override_user):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)

        resp = client.post(
            "/tasks",
            json={
                "fund_id": fund_id,
                "title": "Solo work",
                "assigned_to_user_id": fm_id,
            },
        )
        assert resp.status_code == 201
        assert _list_notifications(fm_id) == []

    def test_task_patch_reassignment_notifies_new_assignee(
        self, client, override_user
    ):
        org_id = _seed_org()
        fm_id = _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,
        )
        new_assignee_id = _seed_user(
            "hanko-new",
            UserRole.lp,
            email="new@example.com",
            organization_id=org_id,
        )
        override_user("hanko-fm")
        fund_id = _seed_fund(org_id)
        # Seed a task created by fm and originally self-assigned
        db = SessionLocal()
        try:
            task = Task(
                fund_id=fund_id,
                title="Reassign me",
                assigned_to_user_id=fm_id,
                created_by_user_id=fm_id,
            )
            db.add(task)
            db.commit()
            task_id = task.id
        finally:
            db.close()

        # Sanity: no notifications yet
        assert _list_notifications(new_assignee_id) == []

        resp = client.patch(
            f"/tasks/{task_id}",
            json={"assigned_to_user_id": new_assignee_id},
        )
        assert resp.status_code == 200
        rows = _list_notifications(new_assignee_id)
        assert len(rows) == 1
        assert rows[0].related_type == "task"


def test_repository_marks_read_idempotently():
    """Calling mark_read on an already-read notification should not bump read_at."""
    from app.repositories.notification_repository import NotificationRepository

    user_id = _seed_user("hanko-me", UserRole.lp)
    db = SessionLocal()
    try:
        repo = NotificationRepository(db)
        n = repo.create(user_id=user_id, title="t", message="m")
        first = repo.mark_read(n.id)
        assert first.status is NotificationStatus.read
        # Stamp a sentinel value and confirm a second mark_read leaves it alone.
        sentinel = datetime(2000, 1, 1)
        first.read_at = sentinel
        db.commit()
        second = repo.mark_read(n.id)
        assert second.status is NotificationStatus.read
        assert second.read_at.replace(tzinfo=None) == sentinel
    finally:
        db.close()
