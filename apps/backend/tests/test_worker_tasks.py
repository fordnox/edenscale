"""Tests for the arq email tasks in ``app.tasks`` and the overdue cron repo.

``app.services.email.send_email`` is monkeypatched to capture calls, so the
tasks run end-to-end (session, joins, template rendering) without SMTP.
Tasks are coroutines; they're driven with a fresh event loop per call, same
as ``test_hanko_service``.
"""

import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.models import (
    CapitalCall,
    CapitalCallItem,
    CapitalCallStatus,
    Commitment,
    CommitmentStatus,
    Distribution,
    DistributionItem,
    DistributionStatus,
    Document,
    DocumentType,
    Fund,
    Investor,
    InvestorContact,
    Organization,
    OrganizationInvitation,
    OrganizationType,
    User,
    UserRole,
)
from app.models.enums import InvitationStatus
from app.repositories.capital_call_repository import CapitalCallRepository
from app import tasks


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture ``app.services.email.send_email`` calls; never hits SMTP."""
    calls: list[dict] = []

    def _capture(to, subject, html, text=None, *, context=None):
        calls.append(
            {"to": to, "subject": subject, "html": html, "context": context or {}}
        )
        return True

    monkeypatch.setattr("app.services.email.send_email", _capture)
    return calls


def _seed_base(currency: str = "USD"):
    """Org + fund + investor + primary contact + commitment; returns ids."""
    org = Organization(
        name="NewTaven Capital",
        slug=slugify("NewTaven Capital"),
        type=OrganizationType.fund_manager_firm,
    )
    db = SessionLocal()
    try:
        db.add(org)
        db.flush()
        fund = Fund(
            organization_id=org.id,
            name="Fund I",
            slug=slugify("Fund I"),
            currency_code=currency,
        )
        investor = Investor(organization_id=org.id, name="Anand Family Office")
        db.add_all([fund, investor])
        db.flush()
        contact = InvestorContact(
            investor_id=investor.id,
            first_name="Priya",
            last_name="Anand",
            email="priya@example.com",
            is_primary=True,
        )
        commitment = Commitment(
            fund_id=fund.id,
            investor_id=investor.id,
            committed_amount=Decimal("5000000.00"),
            called_amount=Decimal("3250000.00"),
            distributed_amount=Decimal("100000.00"),
            commitment_date=date(2026, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add_all([contact, commitment])
        db.commit()
        return {
            "org_id": org.id,
            "fund_id": fund.id,
            "investor_id": investor.id,
            "contact_id": contact.id,
            "commitment_id": commitment.id,
        }
    finally:
        db.close()


class TestCapitalCallEmails:
    def test_emails_primary_contacts_with_commitment_figures(self, sent_emails):
        ids = _seed_base()
        db = SessionLocal()
        try:
            # A second, non-primary contact must not receive an email.
            db.add(
                InvestorContact(
                    investor_id=ids["investor_id"],
                    first_name="Backup",
                    last_name="Person",
                    email="backup@example.com",
                    is_primary=False,
                )
            )
            call = CapitalCall(
                fund_id=ids["fund_id"],
                title="Capital Call No. 4",
                description="Follow-on acquisition.",
                due_date=date(2026, 7, 22),
                call_date=date(2026, 7, 1),
                amount=Decimal("250000.00"),
                status=CapitalCallStatus.sent,
            )
            db.add(call)
            db.flush()
            db.add(
                CapitalCallItem(
                    capital_call_id=call.id,
                    commitment_id=ids["commitment_id"],
                    amount_due=Decimal("250000.00"),
                )
            )
            db.commit()
            call_id = str(call.id)
        finally:
            db.close()

        sent = _run(tasks.task_send_capital_call_emails({}, call_id))

        assert sent == 1
        assert len(sent_emails) == 1
        mail = sent_emails[0]
        assert mail["to"] == "priya@example.com"
        assert "Capital Call No. 4" in mail["subject"]
        ctx = mail["context"]
        assert ctx["recipient_name"] == "Priya Anand"
        assert ctx["investor_name"] == "Anand Family Office"
        assert ctx["fund_name"] == "Fund I"
        assert ctx["amount_due"] == "250,000.00 USD"
        assert ctx["committed_amount"] == "5,000,000.00 USD"
        assert ctx["called_to_date"] == "3,250,000.00 USD"
        # unfunded = committed - called
        assert ctx["unfunded_amount"] == "1,750,000.00 USD"
        assert "250,000.00 USD" in mail["html"]

    def test_missing_call_is_a_noop(self, sent_emails):
        assert _run(tasks.task_send_capital_call_emails({}, str(uuid.uuid4()))) == 0
        assert sent_emails == []


class TestDistributionEmails:
    def test_emails_primary_contacts(self, sent_emails):
        ids = _seed_base()
        db = SessionLocal()
        try:
            distribution = Distribution(
                fund_id=ids["fund_id"],
                title="Distribution No. 2",
                distribution_date=date(2026, 8, 15),
                amount=Decimal("100000.00"),
                status=DistributionStatus.sent,
            )
            db.add(distribution)
            db.flush()
            db.add(
                DistributionItem(
                    distribution_id=distribution.id,
                    commitment_id=ids["commitment_id"],
                    amount_due=Decimal("100000.00"),
                )
            )
            db.commit()
            distribution_id = str(distribution.id)
        finally:
            db.close()

        sent = _run(tasks.task_send_distribution_emails({}, distribution_id))

        assert sent == 1
        mail = sent_emails[0]
        assert mail["to"] == "priya@example.com"
        assert "Distribution No. 2" in mail["subject"]
        ctx = mail["context"]
        assert ctx["amount_receivable"] == "100,000.00 USD"
        assert ctx["payment_date"] == "August 15, 2026"


class TestInvitationEmail:
    def test_pending_invitation_sends_with_accept_url(self, sent_emails):
        ids = _seed_base()
        db = SessionLocal()
        try:
            inviter = User(
                role=UserRole.admin,
                first_name="Eleanor",
                last_name="Vance",
                email="eleanor@example.com",
                hanko_subject_id="hanko-inviter",
            )
            db.add(inviter)
            db.flush()
            invitation = OrganizationInvitation(
                organization_id=ids["org_id"],
                email="alex@example.com",
                role=UserRole.lp,
                token="tok-worker-1",
                invited_by_user_id=inviter.id,
            )
            db.add(invitation)
            db.commit()
            invitation_id = str(invitation.id)
        finally:
            db.close()

        sent = _run(tasks.task_send_invitation_email({}, invitation_id))

        assert sent == 1
        mail = sent_emails[0]
        assert mail["to"] == "alex@example.com"
        ctx = mail["context"]
        assert ctx["organization_name"] == "NewTaven Capital"
        assert ctx["inviter_name"] == "Eleanor Vance"
        assert ctx["role_label"] == "Limited Partner"
        assert ctx["accept_url"].endswith("/invitations/accept?token=tok-worker-1")
        assert "tok-worker-1" in mail["html"]

    def test_non_pending_invitation_is_skipped(self, sent_emails, caplog):
        ids = _seed_base()
        db = SessionLocal()
        try:
            invitation = OrganizationInvitation(
                organization_id=ids["org_id"],
                email="alex@example.com",
                role=UserRole.lp,
                token="tok-worker-2",
                status=InvitationStatus.revoked,
            )
            db.add(invitation)
            db.commit()
            invitation_id = str(invitation.id)
        finally:
            db.close()

        with caplog.at_level("WARNING"):
            sent = _run(tasks.task_send_invitation_email({}, invitation_id))

        assert sent == 0
        assert sent_emails == []
        assert any("not pending" in r.message for r in caplog.records)

    def test_missing_invitation_is_skipped(self, sent_emails, caplog):
        with caplog.at_level("WARNING"):
            assert _run(tasks.task_send_invitation_email({}, str(uuid.uuid4()))) == 0
        assert sent_emails == []
        assert any("not found" in r.message for r in caplog.records)


class TestWelcomeEmail:
    def test_sends_to_the_user(self, sent_emails):
        ids = _seed_base()
        db = SessionLocal()
        try:
            user = User(
                role=UserRole.lp,
                first_name="Alex",
                last_name="Rivera",
                email="alex@example.com",
                hanko_subject_id="hanko-alex",
            )
            db.add(user)
            db.commit()
            user_id = str(user.id)
        finally:
            db.close()

        sent = _run(tasks.task_send_welcome_email({}, user_id, str(ids["org_id"])))

        assert sent == 1
        mail = sent_emails[0]
        assert mail["to"] == "alex@example.com"
        assert mail["context"]["organization_name"] == "NewTaven Capital"
        assert mail["context"]["recipient_name"] == "Alex"


class TestDocumentEmail:
    def _seed_document(self, ids, **overrides):
        db = SessionLocal()
        try:
            document = Document(
                organization_id=ids["org_id"],
                document_type=DocumentType.report,
                title="Q2 2026 Fund Report",
                file_name="report.pdf",
                file_url="https://storage.example.com/report.pdf",
                **overrides,
            )
            db.add(document)
            db.commit()
            return str(document.id)
        finally:
            db.close()

    def test_investor_scoped_document_emails_contacts_even_if_confidential(
        self, sent_emails
    ):
        ids = _seed_base()
        document_id = self._seed_document(
            ids, investor_id=ids["investor_id"], is_confidential=True
        )
        sent = _run(tasks.task_send_document_email({}, document_id))
        assert sent == 1
        assert sent_emails[0]["to"] == "priya@example.com"
        assert "Q2 2026 Fund Report" in sent_emails[0]["subject"]

    def test_fund_scoped_confidential_document_emails_nobody(self, sent_emails):
        ids = _seed_base()
        document_id = self._seed_document(
            ids, fund_id=ids["fund_id"], is_confidential=True
        )
        assert _run(tasks.task_send_document_email({}, document_id)) == 0
        assert sent_emails == []

    def test_fund_scoped_public_document_emails_committed_primary_contacts(
        self, sent_emails
    ):
        ids = _seed_base()
        document_id = self._seed_document(
            ids, fund_id=ids["fund_id"], is_confidential=False
        )
        sent = _run(tasks.task_send_document_email({}, document_id))
        assert sent == 1
        assert sent_emails[0]["to"] == "priya@example.com"
        assert sent_emails[0]["context"]["fund_name"] == "Fund I"


class TestMarkOverdueCron:
    def test_only_past_due_sent_calls_flip(self):
        ids = _seed_base()
        past = date.today() - timedelta(days=3)
        future = date.today() + timedelta(days=3)
        db = SessionLocal()
        try:
            overdue_sent = CapitalCall(
                fund_id=ids["fund_id"],
                title="Past-due sent",
                due_date=past,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.sent,
            )
            overdue_partial = CapitalCall(
                fund_id=ids["fund_id"],
                title="Past-due partially paid",
                due_date=past,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.partially_paid,
            )
            stale_draft = CapitalCall(
                fund_id=ids["fund_id"],
                title="Past-due draft",
                due_date=past,
                amount=Decimal("1.00"),
                status=CapitalCallStatus.draft,
            )
            fresh_sent = CapitalCall(
                fund_id=ids["fund_id"],
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
        ids = _seed_base()
        db = SessionLocal()
        try:
            db.add(
                CapitalCall(
                    fund_id=ids["fund_id"],
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


class TestEnqueueOrLog:
    def test_swallows_enqueue_failures(self, monkeypatch, caplog):
        async def _boom(*_args, **_kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr(tasks, "enqueue_task", _boom)
        with caplog.at_level("WARNING"):
            result = _run(tasks.enqueue_or_log("task_ping"))
        assert result is None
        assert any("Failed to enqueue" in r.message for r in caplog.records)
