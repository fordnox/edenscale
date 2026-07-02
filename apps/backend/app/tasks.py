"""arq task functions and enqueue helpers.

Task functions run inside the arq worker (see ``app.worker.WorkerSettings``).
Each task opens its own ``SessionLocal`` and closes it in ``finally``; email
delivery goes through ``app.services.email`` (accessed via the module so tests
can monkeypatch ``app.services.email.send_email``) and is pushed to a thread
with ``asyncio.to_thread`` since SMTP is blocking.

API routers must enqueue through :func:`enqueue_or_log` — a Redis outage must
never fail the originating request.
"""

import asyncio
import logging
import uuid
from datetime import date
from decimal import Decimal

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.distribution import Distribution
from app.models.distribution_item import DistributionItem
from app.models.document import Document
from app.models.enums import InvitationStatus, UserRole
from app.models.fund import Fund
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.services import email as email_service

logger = logging.getLogger(__name__)

# Redis connection settings. A single connection attempt only — enqueues
# happen inside API requests, and arq's default 5×1s retry loop would stall
# the request for seconds whenever Redis is down.
redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
redis_settings.conn_retries = 1

# Upper bound on how long a request-path enqueue may take before
# enqueue_or_log gives up (connection + enqueue round-trip).
_ENQUEUE_TIMEOUT_SECONDS = 3.0


async def get_redis_pool():
    """Get or create Redis pool for arq"""
    return await create_pool(redis_settings, default_queue_name=settings.APP_DOMAIN)


async def enqueue_task(task_name: str, *args, **kwargs):
    """
    Enqueue a task to the arq worker.

    Args:
        task_name: Name of the task function
        *args: Positional arguments for the task
        **kwargs: Keyword arguments for the task

    Returns:
        Job object from arq
    """
    pool = await get_redis_pool()
    try:
        job = await pool.enqueue_job(task_name, *args, **kwargs)
        return job
    finally:
        await pool.aclose()


async def enqueue_or_log(task_name: str, *args):
    """Enqueue a task, swallowing every failure.

    Routers use this for fire-and-forget side effects — Redis being down must
    never fail an API request. Returns the arq job or ``None`` on failure.
    """
    try:
        return await asyncio.wait_for(
            enqueue_task(task_name, *args), timeout=_ENQUEUE_TIMEOUT_SECONDS
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad
        logger.warning("Failed to enqueue task %s: %s", task_name, exc)
        return None


# ===== Formatting helpers =====

_ROLE_LABELS: dict[UserRole, str] = {
    UserRole.superadmin: "Superadmin",
    UserRole.admin: "Admin",
    UserRole.fund_manager: "Fund Manager",
    UserRole.lp: "Limited Partner",
}

_DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "legal": "Legal Document",
    "kyc_aml": "KYC/AML Document",
    "financial": "Financial Document",
    "report": "Fund Report",
    "notice": "Notice",
    "other": "Document",
}


def _app_base_url() -> str:
    return settings.APP_DOMAIN_URL.rstrip("/")


def _build_accept_url(token) -> str:
    return f"{_app_base_url()}/invitations/accept?token={token}"


def _fmt_money(amount, currency_code=None) -> str:
    if amount is None:
        return "—"
    value = f"{Decimal(amount):,.2f}"
    return f"{value} {currency_code}" if currency_code else value


def _fmt_date(value) -> str:
    if value is None:
        return "—"
    return f"{value:%B} {value.day}, {value.year}"


def _contact_name(contact: InvestorContact) -> str:
    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    return name or "investor"


async def _deliver(to, subject: str, template: str, params: dict) -> bool:
    """Render ``template`` with ``params`` and send it off-thread."""
    html = email_service.render_template(template, **params)
    return await asyncio.to_thread(
        email_service.send_email, to, subject, html, context=params
    )


# ===== Example Tasks =====
async def enqueue_task_ping():
    """Enqueue a simple ping task for testing"""
    return await enqueue_task("task_ping")


async def task_ping(ctx: dict) -> str:
    """Worker function for the `task_ping` job enqueued by `enqueue_task_ping`."""
    logger.info("task_ping executed")
    return "pong"


# ===== Email Tasks =====


async def task_send_invitation_email(ctx: dict, invitation_id: str) -> int:
    """Send the invitation email for a pending organization invitation."""
    db = SessionLocal()
    try:
        invitation = (
            db.query(OrganizationInvitation)
            .filter(OrganizationInvitation.id == uuid.UUID(invitation_id))
            .first()
        )
        if invitation is None:
            logger.warning("task_send_invitation_email: %s not found", invitation_id)
            return 0
        if invitation.status is not InvitationStatus.pending:
            logger.warning(
                "task_send_invitation_email: %s not pending (status=%s)",
                invitation_id,
                invitation.status.value,
            )
            return 0
        organization = invitation.organization
        inviter = invitation.invited_by
        org_name = organization.name if organization is not None else "NewTaven"
        inviter_name = (
            f"{inviter.first_name or ''} {inviter.last_name or ''}".strip()
            if inviter is not None
            else ""
        ) or f"The team at {org_name}"
        params = {
            "organization_name": org_name,
            "inviter_name": inviter_name,
            "role_label": _ROLE_LABELS.get(invitation.role, "member"),  # type: ignore[no-matching-overload]
            "accept_url": _build_accept_url(invitation.token),
            "invitee_email": invitation.email,
            "expires_at": _fmt_date(invitation.expires_at),
        }
        sent = await _deliver(
            invitation.email,
            f"You're invited to join {org_name} on NewTaven",
            "invite_user",
            params,
        )
        return 1 if sent else 0
    finally:
        db.close()


def _primary_contact_rows(db, item_model, item_fk, parent_id):
    """(item, commitment, investor, contact) rows for a call/distribution.

    Mirrors the join used by the send-route in-app notifications, but resolves
    the primary contact rows (with an email address) instead of user ids.
    """
    return (
        db.query(item_model, Commitment, Investor, InvestorContact)
        .join(Commitment, Commitment.id == item_model.commitment_id)
        .join(Investor, Investor.id == Commitment.investor_id)
        .join(InvestorContact, InvestorContact.investor_id == Investor.id)
        .filter(
            item_fk == parent_id,
            InvestorContact.is_primary.is_(True),
            InvestorContact.email.is_not(None),
        )
        .all()
    )


async def task_send_capital_call_emails(ctx: dict, call_id: str) -> int:
    """Email every primary investor contact their capital-call allocation."""
    db = SessionLocal()
    try:
        call = (
            db.query(CapitalCall).filter(CapitalCall.id == uuid.UUID(call_id)).first()
        )
        if call is None:
            logger.warning("task_send_capital_call_emails: %s not found", call_id)
            return 0
        fund = db.query(Fund).filter(Fund.id == call.fund_id).first()
        if fund is None:
            logger.warning(
                "task_send_capital_call_emails: fund missing for call %s", call_id
            )
            return 0
        organization = (
            db.query(Organization)
            .filter(Organization.id == fund.organization_id)
            .first()
        )
        org_name = organization.name if organization is not None else "NewTaven"
        currency = fund.currency_code or "USD"
        view_url = (
            f"{_app_base_url()}/app/{organization.slug}/calls"
            if organization is not None
            else _app_base_url()
        )
        rows = _primary_contact_rows(
            db, CapitalCallItem, CapitalCallItem.capital_call_id, call.id
        )
        sent_count = 0
        for item, commitment, investor, contact in rows:
            committed = Decimal(commitment.committed_amount or 0)
            called = Decimal(commitment.called_amount or 0)
            unfunded = committed - called
            params = {
                "call_title": call.title,
                "recipient_name": _contact_name(contact),
                "organization_name": org_name,
                "investor_name": investor.name,
                "fund_name": fund.name,
                "currency_code": currency,
                "amount_due": _fmt_money(item.amount_due, currency),
                "due_date": _fmt_date(call.due_date),
                "call_date": _fmt_date(call.call_date),
                "committed_amount": _fmt_money(committed, currency),
                "called_to_date": _fmt_money(called, currency),
                "unfunded_amount": _fmt_money(unfunded, currency),
                "view_url": view_url,
                "description": call.description or "",
            }
            if await _deliver(
                contact.email,
                f"Capital call: {call.title} — {fund.name}",
                "capital_call",
                params,
            ):
                sent_count += 1
        return sent_count
    finally:
        db.close()


async def task_send_distribution_emails(ctx: dict, distribution_id: str) -> int:
    """Email every primary investor contact their distribution allocation."""
    db = SessionLocal()
    try:
        distribution = (
            db.query(Distribution)
            .filter(Distribution.id == uuid.UUID(distribution_id))
            .first()
        )
        if distribution is None:
            logger.warning(
                "task_send_distribution_emails: %s not found", distribution_id
            )
            return 0
        fund = db.query(Fund).filter(Fund.id == distribution.fund_id).first()
        if fund is None:
            logger.warning(
                "task_send_distribution_emails: fund missing for %s", distribution_id
            )
            return 0
        organization = (
            db.query(Organization)
            .filter(Organization.id == fund.organization_id)
            .first()
        )
        org_name = organization.name if organization is not None else "NewTaven"
        currency = fund.currency_code or "USD"
        view_url = (
            f"{_app_base_url()}/app/{organization.slug}/distributions"
            if organization is not None
            else _app_base_url()
        )
        rows = _primary_contact_rows(
            db, DistributionItem, DistributionItem.distribution_id, distribution.id
        )
        sent_count = 0
        for item, commitment, investor, contact in rows:
            params = {
                "distribution_title": distribution.title,
                "recipient_name": _contact_name(contact),
                "organization_name": org_name,
                "investor_name": investor.name,
                "fund_name": fund.name,
                "currency_code": currency,
                "amount_receivable": _fmt_money(item.amount_due, currency),
                "payment_date": _fmt_date(distribution.distribution_date),
                "committed_amount": _fmt_money(commitment.committed_amount, currency),
                "distributed_to_date": _fmt_money(
                    commitment.distributed_amount, currency
                ),
                "view_url": view_url,
                "description": distribution.description or "",
            }
            if await _deliver(
                contact.email,
                f"Distribution notice: {distribution.title} — {fund.name}",
                "distribution",
                params,
            ):
                sent_count += 1
        return sent_count
    finally:
        db.close()


async def task_send_welcome_email(ctx: dict, user_id: str, organization_id: str) -> int:
    """Send the welcome email after a user joins an organization."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if user is None or not user.email:
            logger.warning("task_send_welcome_email: user %s not found", user_id)
            return 0
        organization = (
            db.query(Organization)
            .filter(Organization.id == uuid.UUID(organization_id))
            .first()
        )
        org_name = organization.name if organization is not None else "NewTaven"
        params = {
            "recipient_name": (user.first_name or "").strip() or "there",
            "organization_name": org_name,
            "app_url": f"{_app_base_url()}/app",
            "recipient_email": user.email,
        }
        sent = await _deliver(user.email, "Welcome to NewTaven", "welcome", params)
        return 1 if sent else 0
    finally:
        db.close()


def _document_contacts(db, document: Document) -> list[InvestorContact]:
    """Contacts to email about a new document.

    The visibility rule lives in ``DocumentRepository.recipient_contacts``
    (shared with the router's in-app notifications); this keeps only contacts
    with an email address.
    """
    contacts = DocumentRepository(db).recipient_contacts(document)
    return [contact for contact in contacts if contact.email]


async def task_send_document_email(ctx: dict, document_id: str) -> int:
    """Notify investor contacts that a document was uploaded."""
    db = SessionLocal()
    try:
        document = (
            db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        )
        if document is None:
            logger.warning("task_send_document_email: %s not found", document_id)
            return 0
        contacts = _document_contacts(db, document)
        if not contacts:
            return 0
        fund = document.fund
        organization = document.organization
        if organization is None and fund is not None:
            organization = fund.organization
        org_name = organization.name if organization is not None else "NewTaven"
        view_url = (
            f"{_app_base_url()}/app/{organization.slug}/documents"
            if organization is not None
            else _app_base_url()
        )
        doc_type = (
            document.document_type.value
            if document.document_type is not None
            else "other"
        )
        sent_count = 0
        for contact in contacts:
            params = {
                "document_title": document.title,
                "document_type_label": _DOCUMENT_TYPE_LABELS.get(doc_type, "Document"),
                "recipient_name": _contact_name(contact),
                "organization_name": org_name,
                "fund_name": fund.name if fund is not None else "—",
                "uploaded_at": _fmt_date(document.created_at),
                "view_url": view_url,
            }
            if await _deliver(
                contact.email,
                f"New document: {document.title}",
                "document_uploaded",
                params,
            ):
                sent_count += 1
        return sent_count
    finally:
        db.close()


async def cron_mark_overdue_capital_calls(ctx: dict) -> int:
    """Daily cron: flip past-due sent/partially_paid capital calls to overdue."""
    from app.repositories.capital_call_repository import CapitalCallRepository

    db = SessionLocal()
    try:
        count = CapitalCallRepository(db).mark_overdue(date.today())
        logger.info("cron_mark_overdue_capital_calls: marked %d call(s) overdue", count)
        return count
    finally:
        db.close()
