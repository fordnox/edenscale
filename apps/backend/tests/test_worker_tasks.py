"""Tests for the notification worker (``task_send_notification``) and the
overdue-capital-call cron.

Email delivery is off in tests (no ``RESEND_API_KEY``), so the email channel
returns a ``disabled`` result and the task logs a ``skipped`` NotificationLog
row without ever touching Resend. The in-app Notification row is still written.
Tasks are coroutines; they're driven with a fresh event loop per call.
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import tasks
from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.models import (
    CapitalCall,
    CapitalCallStatus,
    Fund,
    Notification,
    NotificationLog,
    Organization,
    OrganizationType,
    User,
)
from app.repositories.capital_call_repository import CapitalCallRepository
from app.repositories.notification_log_repository import NotificationLogRepository
from app.worker import task_send_notification


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_org_and_user(email: str = "lp@example.com"):
    """Org + a user belonging to it; returns (org_id, user_id)."""
    db = SessionLocal()
    try:
        org = Organization(
            name="NewTaven Capital",
            slug=slugify("NewTaven Capital"),
            type=OrganizationType.fund_manager_firm,
        )
        db.add(org)
        db.flush()
        user = User(
            email=email,
            first_name="Priya",
            last_name="Anand",
        )
        db.add(user)
        db.commit()
        return org.id, user.id
    finally:
        db.close()


def _seed_fund():
    db = SessionLocal()
    try:
        org = Organization(
            name="NewTaven Capital",
            slug=slugify("NewTaven Capital"),
            type=OrganizationType.fund_manager_firm,
        )
        db.add(org)
        db.flush()
        fund = Fund(
            organization_id=org.id,
            name="Fund I",
            slug=slugify("Fund I"),
            currency_code="USD",
        )
        db.add(fund)
        db.commit()
        return fund.id
    finally:
        db.close()


class _FakeChannel:
    """Controllable stand-in for ``EmailChannel`` so idempotency tests can
    drive exactly what ``channel.send`` returns (or raises) per call, without
    touching Resend or the real channel implementation."""

    channel_name = "email"

    def __init__(self, results):
        self._results = list(results)
        self.calls: list[dict] = []

    async def send(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._results.pop(0) if self._results else self._results[-1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _FakeRegistry:
    def __init__(self, channel):
        self._channel = channel

    def get(self, channel_name):
        return self._channel if channel_name == "email" else None


class TestSendNotification:
    def test_writes_inapp_row_and_skipped_email_log(self):
        org_id, user_id = _seed_org_and_user()

        _run(
            task_send_notification(
                {},
                user_id=str(user_id),
                organization_id=str(org_id),
                notification_type="customer.welcome",
                title="Welcome to NewTaven",
                message="Your account is ready.",
                data={"recipient_name": "Priya"},
                reference_type="organization",
                reference_id=str(org_id),
            )
        )

        db = SessionLocal()
        try:
            notes = db.query(Notification).filter(Notification.user_id == user_id).all()
            assert len(notes) == 1
            assert notes[0].title == "Welcome to NewTaven"
            assert notes[0].related_type == "organization"

            logs = db.query(NotificationLog).all()
            assert len(logs) == 1
            assert logs[0].channel == "email"
            assert logs[0].recipient == "lp@example.com"
            assert logs[0].notification_type == "customer.welcome"
            # No RESEND_API_KEY in tests → delivery skipped, not attempted.
            assert logs[0].status == "skipped"
        finally:
            db.close()

    def test_email_only_when_no_user(self):
        org_id, _ = _seed_org_and_user()

        _run(
            task_send_notification(
                {},
                user_id=None,
                organization_id=str(org_id),
                notification_type="customer.invitation",
                title="You're invited",
                message="Join us",
                data={"recipient_email": "invitee@example.com"},
                reference_type="invitation",
                reference_id=str(uuid.uuid4()),
            )
        )

        db = SessionLocal()
        try:
            assert db.query(Notification).count() == 0
            logs = db.query(NotificationLog).all()
            assert len(logs) == 1
            assert logs[0].recipient == "invitee@example.com"
            assert logs[0].user_id is None
        finally:
            db.close()

    def test_missing_user_is_a_noop(self):
        _run(
            task_send_notification(
                {},
                user_id=str(uuid.uuid4()),
                organization_id=None,
                notification_type="customer.welcome",
                title="Welcome",
                message="hi",
                data={},
            )
        )
        db = SessionLocal()
        try:
            assert db.query(Notification).count() == 0
            assert db.query(NotificationLog).count() == 0
        finally:
            db.close()


class TestNotificationIdempotency:
    """Plan 014: the idempotency key that makes it safe to let
    ``task_send_notification`` raise instead of swallowing every exception.
    """

    def test_transient_failure_propagates(self, monkeypatch):
        """A transient failure inside the task must raise, not report success.

        This is the regression test for the bug plan 014 fixes: pre-fix,
        ``task_send_notification`` wrapped everything in a bare
        ``except Exception`` and logged-and-swallowed, so arq saw the job as
        successful and never retried. Verified to FAIL against the pre-fix
        code (that code catches this RuntimeError and returns ``None``
        instead of raising) — see the plan 014 report for the before/after.
        """
        org_id, user_id = _seed_org_and_user()
        channel = _FakeChannel([RuntimeError("Resend is down")])
        monkeypatch.setattr(
            "app.worker.get_default_registry", lambda: _FakeRegistry(channel)
        )

        with pytest.raises(RuntimeError, match="Resend is down"):
            _run(
                task_send_notification(
                    {},
                    user_id=str(user_id),
                    organization_id=str(org_id),
                    notification_type="customer.welcome",
                    title="Welcome to NewTaven",
                    message="Your account is ready.",
                    data={"recipient_name": "Priya"},
                    reference_type="organization",
                    reference_id=str(org_id),
                )
            )

    def test_retry_does_not_resend_already_delivered_channel(self, monkeypatch):
        """The test that matters most: a retry after a successful send must
        not re-send an already-delivered channel — the idempotency key is
        what makes it safe to let failures propagate and arq retry the job.
        """
        org_id, user_id = _seed_org_and_user()
        channel = _FakeChannel([{"success": True}])
        monkeypatch.setattr(
            "app.worker.get_default_registry", lambda: _FakeRegistry(channel)
        )

        kwargs = dict(
            user_id=str(user_id),
            organization_id=str(org_id),
            notification_type="customer.welcome",
            title="Welcome to NewTaven",
            message="Your account is ready.",
            data={"recipient_name": "Priya"},
            reference_type="organization",
            reference_id=str(org_id),
        )

        _run(task_send_notification({}, **kwargs))
        assert len(channel.calls) == 1

        db = SessionLocal()
        try:
            logs = db.query(NotificationLog).all()
            assert len(logs) == 1
            assert logs[0].status == "sent"
        finally:
            db.close()

        # Simulate arq re-invoking the same job after a retry (e.g. it raised
        # on a later step in the real multi-channel case). The already-sent
        # channel must not be re-sent.
        _run(task_send_notification({}, **kwargs))
        assert len(channel.calls) == 1, "email channel was re-sent on retry"

        db = SessionLocal()
        try:
            logs = db.query(NotificationLog).all()
            # Still one row: the unique constraint identifies one delivery,
            # and the retry updates it in place rather than inserting again.
            assert len(logs) == 1
            assert logs[0].status == "sent"
        finally:
            db.close()

    def test_failed_delivery_is_retried_not_skipped(self, monkeypatch):
        """A channel that failed (never delivered) IS retried — only a
        terminal (``sent``/``skipped``) outcome is treated as already done."""
        org_id, user_id = _seed_org_and_user()
        channel = _FakeChannel(
            [{"success": False, "error": "boom"}, {"success": True}]
        )
        monkeypatch.setattr(
            "app.worker.get_default_registry", lambda: _FakeRegistry(channel)
        )

        kwargs = dict(
            user_id=str(user_id),
            organization_id=str(org_id),
            notification_type="customer.welcome",
            title="Welcome to NewTaven",
            message="Your account is ready.",
            data={"recipient_name": "Priya"},
            reference_type="organization",
            reference_id=str(org_id),
        )

        _run(task_send_notification({}, **kwargs))
        db = SessionLocal()
        try:
            logs = db.query(NotificationLog).all()
            assert len(logs) == 1
            assert logs[0].status == "failed"
        finally:
            db.close()

        _run(task_send_notification({}, **kwargs))
        assert len(channel.calls) == 2, "a failed channel should be retried"

        db = SessionLocal()
        try:
            logs = db.query(NotificationLog).all()
            # Updated in place, not a second row.
            assert len(logs) == 1
            assert logs[0].status == "sent"
        finally:
            db.close()

    def test_missing_organization_is_a_noop(self):
        """FK guard survives the fix: a deleted organization still returns
        early without raising — a genuinely missing row is not retryable."""
        _, user_id = _seed_org_and_user()
        _run(
            task_send_notification(
                {},
                user_id=str(user_id),
                organization_id=str(uuid.uuid4()),
                notification_type="customer.welcome",
                title="Welcome",
                message="hi",
                data={},
            )
        )
        db = SessionLocal()
        try:
            assert db.query(Notification).count() == 0
            assert db.query(NotificationLog).count() == 0
        finally:
            db.close()

    def test_same_reference_different_channels_both_delivered(self):
        """The unique constraint keys on channel too — it must not over-dedupe
        two different channels delivering the same underlying notification."""
        db = SessionLocal()
        try:
            repo = NotificationLogRepository(db)
            key = dict(
                notification_type="customer.capital_call",
                reference_type="capital_call",
                reference_id=str(uuid.uuid4()),
                recipient="lp@example.com",
            )

            email_log = repo.record_delivery(
                notification_id=None,
                user_id=None,
                organization_id=None,
                channel="email",
                subject="Capital call due",
                status="sent",
                provider_response={"success": True},
                error_message=None,
                **key,
            )
            sms_log = repo.record_delivery(
                notification_id=None,
                user_id=None,
                organization_id=None,
                channel="sms",
                subject="Capital call due",
                status="sent",
                provider_response={"success": True},
                error_message=None,
                **key,
            )

            assert email_log.id != sms_log.id
            assert db.query(NotificationLog).count() == 2
            assert repo.is_delivered(channel="email", **key) is True
            assert repo.is_delivered(channel="sms", **key) is True
            assert repo.is_delivered(channel="push", **key) is False
        finally:
            db.close()


class TestMarkOverdueCron:
    def test_only_past_due_sent_calls_flip(self):
        fund_id = _seed_fund()
        past = date.today() - timedelta(days=1)
        future = date.today() + timedelta(days=30)
        db = SessionLocal()
        try:
            overdue_sent = CapitalCall(
                fund_id=fund_id,
                title="Past-due sent",
                due_date=past,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.sent,
            )
            overdue_partial = CapitalCall(
                fund_id=fund_id,
                title="Past-due partially paid",
                due_date=past,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.partially_paid,
            )
            stale_draft = CapitalCall(
                fund_id=fund_id,
                title="Past-due draft",
                due_date=past,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.draft,
            )
            fresh_sent = CapitalCall(
                fund_id=fund_id,
                title="Future sent",
                due_date=future,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.sent,
            )
            db.add_all([overdue_sent, overdue_partial, stale_draft, fresh_sent])
            db.commit()

            count = CapitalCallRepository(db).mark_overdue(date.today())
            assert count == 2

            db.expire_all()
            assert overdue_sent.status is CapitalCallStatus.overdue
            assert overdue_partial.status is CapitalCallStatus.overdue
            assert stale_draft.status is CapitalCallStatus.draft
            assert fresh_sent.status is CapitalCallStatus.sent
        finally:
            db.close()

    def test_cron_task_returns_count(self):
        fund_id = _seed_fund()
        db = SessionLocal()
        try:
            db.add(
                CapitalCall(
                    fund_id=fund_id,
                    title="Past-due sent",
                    due_date=date.today() - timedelta(days=1),
                    amount=Decimal("1.00"),
                    status=CapitalCallStatus.sent,
                )
            )
            db.commit()
        finally:
            db.close()

        assert _run(tasks.cron_mark_overdue_capital_calls({})) == 1
