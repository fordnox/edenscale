import logging
from uuid import UUID

from arq import cron, func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import coerce_notification_type
from app.models.organization import Organization
from app.models.user import User
from app.repositories.notification_log_repository import NotificationLogRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.organization import OrganizationRead
from app.services.channels.registry import get_default_registry
from app.services.drip import deliver_drip_event
from app.tasks import (
    cron_mark_overdue_capital_calls,
    redis_settings,
    task_ping,
)

logger = logging.getLogger(__name__)


async def task_send_notification(
    ctx: dict,
    *,
    user_id: str | None,
    organization_id: str | None,
    notification_type: str,
    title: str,
    message: str | None = None,
    data: dict | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> None:
    """Deliver one notification: write the in-app row, then send each channel.

    ``user_id`` may be ``None`` — an email-only delivery to a recipient with no
    user account (e.g. an invitation). In that case no in-app row is written and
    the email goes to ``data["recipient_email"]``.

    No blanket try/except here: an unexpected failure must propagate so arq
    retries the job (see ``max_tries`` on ``WorkerSettings``). What makes that
    safe is ``NotificationLogRepository`` — before sending a channel we check
    whether it was already delivered for this (type, reference, channel,
    recipient) key, and the delivery is recorded durably (committed) right
    after it succeeds, so a retry never re-sends a channel that already went
    out. Only the FK guards below still return early instead of raising —
    a genuinely missing user/org row is not retryable.
    """
    db = SessionLocal()
    try:
        # FK guards: the recipient/org rows may have been deleted between
        # enqueue and dequeue. Without these, INSERTs would FK-violate and arq
        # would retry the job forever.
        if (
            user_id is not None
            and db.query(User.id).filter(User.id == UUID(user_id)).first() is None
        ):
            logger.warning(
                "Skipping %s notification for missing user %s",
                notification_type,
                user_id,
            )
            return
        org = None
        if organization_id is not None:
            org = (
                db.query(Organization)
                .filter(Organization.id == UUID(organization_id))
                .first()
            )
            if org is None:
                logger.warning(
                    "Skipping %s notification for missing organization %s",
                    notification_type,
                    organization_id,
                )
                return

        nt = coerce_notification_type(notification_type)

        # In-app row — only for a real user. The existing Notification schema
        # stores title/message + a free-form (related_type, related_id); the
        # notification-type string and payload live only on the email/log side.
        notification = None
        if user_id is not None:
            notification = NotificationRepository(db).create(
                user_id=UUID(user_id),
                title=title,
                message=message or "",
                related_type=reference_type,
                related_id=UUID(reference_id) if reference_id else None,
            )

        # Resolve the recipient email: explicit override first, else the user.
        recipient_email = (data or {}).get("recipient_email")
        if not recipient_email and user_id is not None:
            user = db.query(User).filter(User.id == UUID(user_id)).first()
            recipient_email = user.email if user else None

        # Attach org branding so templates can render the logo/name/footer.
        channel_data: dict = dict(data or {})
        if org is not None:
            channel_data["organization"] = OrganizationRead.model_validate(
                org
            ).model_dump(mode="json")

        # Sentinel, not NULL: PostgreSQL treats every NULL as distinct in a
        # unique constraint, so nullable reference columns would silently stop
        # deduping exactly the notification types that have no reference.
        ref_type = reference_type or ""
        ref_id = reference_id or ""
        recipient_value = str(recipient_email or "")

        log_repo = NotificationLogRepository(db)
        registry = get_default_registry()
        for channel_name in ("email",):
            channel = registry.get(channel_name)
            if channel is None:
                continue

            if log_repo.is_delivered(
                notification_type=str(nt),
                reference_type=ref_type,
                reference_id=ref_id,
                channel=channel_name,
                recipient=recipient_value,
            ):
                logger.info(
                    "Skipping already-delivered %s channel: type=%s reference=%s/%s recipient=%s",
                    channel_name,
                    nt,
                    ref_type,
                    ref_id,
                    recipient_value,
                )
                continue

            result = await channel.send(
                recipient_email=recipient_value,
                title=title,
                message=message or "",
                event_type=notification_type,
                data=channel_data,
            )
            if result.get("disabled"):
                status = "skipped"
            elif result.get("success"):
                status = "sent"
            else:
                status = "failed"

            # Committed inside record_delivery, before the next channel is
            # attempted — that's what makes the idempotency check durable
            # across a crash mid-loop.
            log_repo.record_delivery(
                notification_id=notification.id if notification else None,  # type: ignore[invalid-argument-type]
                user_id=UUID(user_id) if user_id else None,
                organization_id=UUID(organization_id) if organization_id else None,
                notification_type=str(nt),
                reference_type=ref_type,
                reference_id=ref_id,
                channel=channel_name,
                recipient=recipient_value,
                subject=title,
                status=status,
                provider_response=result,
                error_message=result.get("error"),
            )

        logger.info(
            "Notification handled: type=%s user=%s recipient=%s",
            notification_type,
            user_id,
            recipient_email,
        )
    finally:
        db.close()


async def task_fire_drip_event(
    ctx: dict,
    *,
    event: str,
    email: str,
    payload: dict,
) -> None:
    """Fire one Resend automation event (e.g. the investor onboarding drip).

    No database work: the payload is built at enqueue time, so unlike
    ``task_send_notification`` there are no rows to guard against.
    """
    result = await deliver_drip_event(event=event, email=email, payload=payload)
    if result.get("success"):
        logger.info("Drip event fired: event=%s recipient=%s", event, email)


async def task_draft_letter(
    ctx: dict,
    *,
    document_id: str,
    user_id: str,
) -> None:
    """Draft a letter from a document with Claude and save it to Letters.

    The document bytes are read server-side and drafted via
    ``app.services.letter_drafting`` (blocking Anthropic call — run off the
    event loop). The result is persisted as an unsent ``Communication`` (type
    ``announcement``) and the requesting manager is notified. Missing document
    or a failed draft is logged and dropped, never retried forever.
    """
    import asyncio

    from app.models.enums import CommunicationType
    from app.repositories.communication_repository import CommunicationRepository
    from app.repositories.document_repository import DocumentRepository
    from app.schemas.communication import CommunicationCreate
    from app.services.letter_drafting import draft_letter
    from app.services.notifications import notify_letter_drafted
    from app.services.storage import get_storage, key_from_file_url

    db = SessionLocal()
    try:
        document = DocumentRepository(db).get(UUID(document_id))
        if document is None:
            logger.warning("task_draft_letter: document %s not found", document_id)
            return

        file_bytes: bytes | None = None
        if document.file_url:
            try:
                file_bytes = get_storage().read(
                    key_from_file_url(document.file_url)  # type: ignore[invalid-argument-type]
                )
            except Exception:
                logger.exception(
                    "task_draft_letter: could not read bytes for document %s",
                    document_id,
                )

        try:
            subject, body = await asyncio.to_thread(
                draft_letter,
                file_bytes=file_bytes,
                mime_type=document.mime_type,  # type: ignore[invalid-argument-type]
                title=document.title,  # type: ignore[invalid-argument-type]
            )
        except Exception:
            logger.exception(
                "task_draft_letter: drafting failed for document %s", document_id
            )
            return

        communication = CommunicationRepository(db).create_draft(
            CommunicationCreate(
                fund_id=document.fund_id,  # type: ignore[invalid-argument-type]
                type=CommunicationType.announcement,
                subject=subject,
                body=body,
            ),
            sender_user_id=UUID(user_id),
        )
        await notify_letter_drafted(
            db,
            communication=communication,
            recipient_user_id=UUID(user_id),
            document_title=document.title,
        )
        logger.info(
            "task_draft_letter: drafted communication %s from document %s",
            communication.id,
            document_id,
        )
    finally:
        db.close()


class WorkerSettings:
    queue_name = settings.APP_DOMAIN
    functions = [
        task_ping,
        # max_tries set explicitly (arq's default is 5) now that failures
        # propagate instead of being swallowed: 3 attempts gives a transient
        # DB/Resend blip room to clear without hammering a genuinely broken
        # delivery for as long as arq's default budget would.
        func(task_send_notification, max_tries=3),  # type: ignore[invalid-argument-type]
        task_fire_drip_event,
        task_draft_letter,
    ]
    cron_jobs = [
        cron(cron_mark_overdue_capital_calls, hour=6, minute=0)  # type: ignore[invalid-argument-type]
    ]
    redis_settings = redis_settings
