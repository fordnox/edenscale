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
