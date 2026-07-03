import logging
from uuid import UUID

from arq import cron

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import coerce_notification_type
from app.models.notification_log import NotificationLog
from app.models.organization import Organization
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.organization import OrganizationRead
from app.services.channels.registry import get_default_registry
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

        registry = get_default_registry()
        for channel_name in ("email",):
            channel = registry.get(channel_name)
            if channel is None:
                continue
            result = await channel.send(
                recipient_email=str(recipient_email or ""),
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

            db.add(
                NotificationLog(
                    notification_id=notification.id if notification else None,
                    user_id=UUID(user_id) if user_id else None,
                    organization_id=UUID(organization_id) if organization_id else None,
                    notification_type=str(nt),
                    channel=channel_name,
                    recipient=recipient_email or "",
                    subject=title,
                    status=status,
                    provider_response=result,
                    error_message=result.get("error"),
                )
            )

        db.commit()
        logger.info(
            "Notification handled: type=%s user=%s recipient=%s",
            notification_type,
            user_id,
            recipient_email,
        )
    except Exception:
        logger.exception(
            "Failed to send notification: type=%s user=%s",
            notification_type,
            user_id,
        )
    finally:
        db.close()


class WorkerSettings:
    queue_name = settings.APP_DOMAIN
    functions = [
        task_ping,
        task_send_notification,
    ]
    cron_jobs = [
        cron(cron_mark_overdue_capital_calls, hour=6, minute=0)  # type: ignore[invalid-argument-type]
    ]
    redis_settings = redis_settings
