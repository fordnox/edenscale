"""Notification fan-out helpers — the single place publishers are called.

Every business event that should notify someone goes through one
``notify_<event>()`` helper here. Routers/repositories never call
``publish_admin_event`` / ``publish_customer_event`` directly, so the payload
shape and the ``try/except`` live in one place and ``grep notify_`` finds every
site a notification can fire.

Each helper:
  1. reads already-persisted ORM objects,
  2. builds a flat, snake_case ``data`` payload (scalars / ISO strings only —
     it becomes the Resend template variable bag, see email_channel.py),
  3. fires the matching publisher(s), and
  4. is wrapped in ``try/except`` so a notification failure never breaks the
     originating write (callers fire-and-forget).

``organization_id`` is always passed so the worker can attach org branding
(``organization_name``, ``organization_slug``, …) to the email variables.
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.event_bus import publish_admin_event, publish_customer_event
from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.distribution import Distribution
from app.models.distribution_item import DistributionItem
from app.models.document import Document
from app.models.enums import (
    AdminNotificationType,
    CustomerNotificationType,
    UserRole,
)
from app.models.fund import Fund
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.task import Task
from app.models.user import User
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


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


def _build_accept_url(token, role) -> str:
    # The gateway only serves the SPAs under their mounts (/manager, /investor);
    # a bare /invitations/accept would land on the marketing site in production.
    mount = "investor" if role is UserRole.lp else "manager"
    return f"{_app_base_url()}/{mount}/invitations/accept?token={token}"


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


def _org_name(organization: Organization | None) -> str:
    return organization.name if organization is not None else "NewTaven"  # type: ignore[invalid-return-type]


def _primary_contact_rows(db: Session, item_model, item_fk, parent_id):
    """(item, commitment, investor, contact) rows for a call/distribution.

    Primary contacts only, and only those that can actually be reached — with a
    linked user (in-app) or an email address (email). The worker delivers
    whichever channels the recipient supports.
    """
    return (
        db.query(item_model, Commitment, Investor, InvestorContact)
        .join(Commitment, Commitment.id == item_model.commitment_id)
        .join(Investor, Investor.id == Commitment.investor_id)
        .join(InvestorContact, InvestorContact.investor_id == Investor.id)
        .filter(
            item_fk == parent_id,
            InvestorContact.is_primary.is_(True),
            (InvestorContact.email.is_not(None))
            | (InvestorContact.user_id.is_not(None)),
        )
        .all()
    )


def _recipient_user_id(contact: InvestorContact) -> str | None:
    return str(contact.user_id) if contact.user_id is not None else None


# ===== Notification helpers =====


async def notify_invitation(db: Session, *, invitation: OrganizationInvitation) -> None:
    """Email a pending organization invitation to the invitee (no user yet)."""
    try:
        organization = invitation.organization
        inviter = invitation.invited_by
        org_name = _org_name(organization)
        inviter_name = (
            f"{inviter.first_name or ''} {inviter.last_name or ''}".strip()
            if inviter is not None
            else ""
        ) or f"The team at {org_name}"
        await publish_customer_event(
            user_id=None,
            organization_id=str(invitation.organization_id),
            event_type=CustomerNotificationType.INVITATION,
            title=f"You're invited to join {org_name} on NewTaven",
            message=f"{inviter_name} invited you to join {org_name}.",
            data={
                "recipient_email": invitation.email,
                "inviter_name": inviter_name,
                "role_label": _ROLE_LABELS.get(invitation.role, "member"),  # type: ignore[no-matching-overload]
                "accept_url": _build_accept_url(invitation.token, invitation.role),
                "invitee_email": invitation.email,
                "expires_at": _fmt_date(invitation.expires_at),
            },
            reference_type="invitation",
            reference_id=str(invitation.id),
        )
    except Exception:
        logger.exception("Invitation %s notify failed", invitation.id)


async def notify_welcome(
    db: Session, *, user: User, organization: Organization
) -> None:
    """Welcome a user who has just joined an organization.

    Email-only (``user_id=None``): the welcome is a pure onboarding email, so
    it does not add a redundant in-app row for the user who just signed in.
    """
    try:
        await publish_customer_event(
            user_id=None,
            organization_id=str(organization.id),
            event_type=CustomerNotificationType.WELCOME,
            title=f"Welcome to {_org_name(organization)}",
            message="Your account is ready.",
            data={
                "recipient_email": user.email,
                "recipient_name": (user.first_name or "").strip() or "there",
                "app_url": f"{_app_base_url()}/investor",
            },
            reference_type="organization",
            reference_id=str(organization.id),
        )
    except Exception:
        logger.exception("Welcome notify failed for user %s", user.id)


async def notify_invitation_accepted(
    db: Session, *, invitation: OrganizationInvitation, accepted_by: User
) -> None:
    """Tell the org's managers that an invitation was accepted."""
    try:
        accepted_name = (
            f"{accepted_by.first_name or ''} {accepted_by.last_name or ''}".strip()
            or accepted_by.email
        )
        await publish_admin_event(
            db,
            organization_id=str(invitation.organization_id),
            event_type=AdminNotificationType.INVITATION_ACCEPTED,
            title="Invitation accepted",
            message=f"{accepted_by.email} accepted an invitation.",
            data={
                "accepted_name": accepted_name,
                "accepted_email": accepted_by.email,
                "role_label": _ROLE_LABELS.get(invitation.role, "member"),  # type: ignore[no-matching-overload]
            },
            reference_type="invitation",
            reference_id=str(invitation.id),
        )
    except Exception:
        logger.exception("Invitation-accepted notify failed for %s", invitation.id)


async def notify_capital_call(db: Session, *, call: CapitalCall) -> None:
    """Notify every primary investor contact of their capital-call allocation."""
    try:
        fund = db.query(Fund).filter(Fund.id == call.fund_id).first()
        if fund is None:
            return
        organization = (
            db.query(Organization)
            .filter(Organization.id == fund.organization_id)
            .first()
        )
        currency = fund.currency_code or "USD"
        view_url = (
            f"{_app_base_url()}/investor/{organization.slug}/calls"
            if organization is not None
            else _app_base_url()
        )
        rows = _primary_contact_rows(
            db, CapitalCallItem, CapitalCallItem.capital_call_id, call.id
        )
        for item, commitment, investor, contact in rows:
            committed = Decimal(commitment.committed_amount or 0)
            called = Decimal(commitment.called_amount or 0)
            unfunded = committed - called
            await publish_customer_event(
                user_id=_recipient_user_id(contact),
                organization_id=(
                    str(organization.id) if organization is not None else None
                ),
                event_type=CustomerNotificationType.CAPITAL_CALL,
                title=f"Capital call: {call.title} — {fund.name}",
                message=f"A capital call for {call.title} has been issued.",
                data={
                    "recipient_email": contact.email,
                    "recipient_name": _contact_name(contact),
                    "call_title": call.title,
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
                },
                reference_type="capital_call",
                reference_id=str(call.id),
            )
    except Exception:
        logger.exception("Capital-call %s notify fan-out failed", call.id)


async def notify_distribution(db: Session, *, distribution: Distribution) -> None:
    """Notify every primary investor contact of their distribution allocation."""
    try:
        fund = db.query(Fund).filter(Fund.id == distribution.fund_id).first()
        if fund is None:
            return
        organization = (
            db.query(Organization)
            .filter(Organization.id == fund.organization_id)
            .first()
        )
        currency = fund.currency_code or "USD"
        view_url = (
            f"{_app_base_url()}/investor/{organization.slug}/distributions"
            if organization is not None
            else _app_base_url()
        )
        rows = _primary_contact_rows(
            db, DistributionItem, DistributionItem.distribution_id, distribution.id
        )
        for item, commitment, investor, contact in rows:
            await publish_customer_event(
                user_id=_recipient_user_id(contact),
                organization_id=(
                    str(organization.id) if organization is not None else None
                ),
                event_type=CustomerNotificationType.DISTRIBUTION,
                title=f"Distribution notice: {distribution.title} — {fund.name}",
                message=f"A distribution for {distribution.title} has been issued.",
                data={
                    "recipient_email": contact.email,
                    "recipient_name": _contact_name(contact),
                    "distribution_title": distribution.title,
                    "investor_name": investor.name,
                    "fund_name": fund.name,
                    "currency_code": currency,
                    "amount_receivable": _fmt_money(item.amount_due, currency),
                    "payment_date": _fmt_date(distribution.distribution_date),
                    "committed_amount": _fmt_money(
                        commitment.committed_amount, currency
                    ),
                    "distributed_to_date": _fmt_money(
                        commitment.distributed_amount, currency
                    ),
                    "view_url": view_url,
                    "description": distribution.description or "",
                },
                reference_type="distribution",
                reference_id=str(distribution.id),
            )
    except Exception:
        logger.exception("Distribution %s notify fan-out failed", distribution.id)


async def notify_document_uploaded(db: Session, *, document: Document) -> None:
    """Notify investor contacts that a document was uploaded."""
    try:
        contacts = DocumentRepository(db).recipient_contacts(document)
        contacts = [c for c in contacts if c.email or c.user_id is not None]
        if not contacts:
            return
        fund = document.fund
        organization = document.organization
        if organization is None and fund is not None:
            organization = fund.organization
        view_url = (
            f"{_app_base_url()}/investor/{organization.slug}/documents"
            if organization is not None
            else _app_base_url()
        )
        doc_type = (
            document.document_type.value
            if document.document_type is not None
            else "other"
        )
        for contact in contacts:
            await publish_customer_event(
                user_id=_recipient_user_id(contact),
                organization_id=(
                    str(organization.id) if organization is not None else None
                ),
                event_type=CustomerNotificationType.DOCUMENT_UPLOADED,
                title=f"New document: {document.title}",
                message=f"A new document '{document.title}' is available.",
                data={
                    "recipient_email": contact.email,
                    "recipient_name": _contact_name(contact),
                    "document_title": document.title,
                    "document_type_label": _DOCUMENT_TYPE_LABELS.get(
                        doc_type, "Document"
                    ),
                    "fund_name": fund.name if fund is not None else "—",
                    "uploaded_at": _fmt_date(document.created_at),
                    "view_url": view_url,
                },
                reference_type="document",
                reference_id=str(document.id),
            )
    except Exception:
        logger.exception("Document %s notify fan-out failed", document.id)


async def notify_commitment_status(
    db: Session, *, commitment: Commitment, fund: Fund
) -> None:
    """Notify an investor's primary contacts that a commitment changed status."""
    try:
        organization = (
            db.query(Organization)
            .filter(Organization.id == fund.organization_id)
            .first()
        )
        status_value = commitment.status.value
        # All linked contacts for the investor (matches the prior in-app fan-out
        # — not just the primary one) plus any with an email address.
        contacts = (
            db.query(InvestorContact)
            .filter(
                InvestorContact.investor_id == commitment.investor_id,
                (InvestorContact.email.is_not(None))
                | (InvestorContact.user_id.is_not(None)),
            )
            .all()
        )
        view_url = (
            f"{_app_base_url()}/investor/{organization.slug}/funds"
            if organization is not None
            else _app_base_url()
        )
        for contact in contacts:
            await publish_customer_event(
                user_id=_recipient_user_id(contact),
                organization_id=(
                    str(organization.id) if organization is not None else None
                ),
                event_type=CustomerNotificationType.COMMITMENT_STATUS,
                title=f"Commitment {status_value}",
                message=f"Your commitment to {fund.name} is now '{status_value}'.",
                data={
                    "recipient_email": contact.email,
                    "recipient_name": _contact_name(contact),
                    "fund_name": fund.name,
                    "status_label": status_value.replace("_", " ").title(),
                    "committed_amount": _fmt_money(
                        commitment.committed_amount, fund.currency_code or "USD"
                    ),
                    "view_url": view_url,
                },
                reference_type="commitment",
                reference_id=str(commitment.id),
            )
    except Exception:
        logger.exception("Commitment %s notify fan-out failed", commitment.id)


async def notify_task_assigned(db: Session, *, task: Task, assignee_user_id) -> None:
    """Notify the assignee that a task was assigned to them."""
    try:
        assignee = db.query(User).filter(User.id == assignee_user_id).first()
        if assignee is None:
            return
        organization = (
            db.query(Organization)
            .filter(Organization.id == assignee.organization_id)
            .first()
            if assignee.organization_id is not None
            else None
        )
        due = _fmt_date(task.due_date) if task.due_date else "—"
        await publish_customer_event(
            user_id=str(assignee.id),
            organization_id=(
                str(organization.id) if organization is not None else None
            ),
            event_type=CustomerNotificationType.TASK_ASSIGNED,
            title=f"Task assigned: {task.title}",
            message=str(task.title),
            data={
                "recipient_email": assignee.email,
                "recipient_name": (assignee.first_name or "").strip() or "there",
                "task_title": task.title,
                "task_description": task.description or "",
                "due_date": due,
                "view_url": f"{_app_base_url()}/manager",
            },
            reference_type="task",
            reference_id=str(task.id),
        )
    except Exception:
        logger.exception("Task %s notify failed", task.id)


async def notify_communication(
    db: Session,
    *,
    communication,
    recipient_user_id=None,
    recipient_email: str | None = None,
) -> None:
    """Notify a single recipient that a communication was sent to them.

    Either a linked user (in-app + email) or a bare email (email only).
    """
    try:
        recipient = (
            db.query(User).filter(User.id == recipient_user_id).first()
            if recipient_user_id is not None
            else None
        )
        organization = (
            db.query(Organization)
            .filter(Organization.id == recipient.organization_id)
            .first()
            if recipient is not None and recipient.organization_id is not None
            else None
        )
        email = recipient_email or (recipient.email if recipient is not None else None)
        await publish_customer_event(
            user_id=str(recipient.id) if recipient is not None else None,
            organization_id=(
                str(organization.id) if organization is not None else None
            ),
            event_type=CustomerNotificationType.COMMUNICATION,
            title=f"New {communication.type.value}: {communication.subject}",
            message=str(communication.subject),
            data={
                "recipient_email": email,
                "communication_type_label": communication.type.value.title(),
                "subject": communication.subject,
                "body_preview": (communication.body or "")[:500],
                "view_url": f"{_app_base_url()}/investor",
            },
            reference_type="communication",
            reference_id=str(communication.id),
        )
    except Exception:
        logger.exception("Communication %s notify failed", communication.id)
