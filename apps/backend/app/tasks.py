"""arq enqueue helpers.

Domain code fans notifications out through ``app.services.notifications`` →
``app.core.event_bus`` → :func:`enqueue_send_notification` here, which drops a
``task_send_notification`` job on the queue. The worker (``app.worker``) does
the actual channel delivery. Enqueues happen inside API requests, so a Redis
outage must never fail or stall the originating request — hence the fast-fail
connection settings and the enqueue timeout.
"""

import asyncio
import logging
from datetime import date

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Redis connection settings. A single connection attempt only — enqueues happen
# inside API requests, and arq's default 5×1s retry loop would stall the request
# for seconds whenever Redis is down.
redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
redis_settings.conn_retries = 1

# Upper bound on how long a request-path enqueue may take before we give up
# (connection + enqueue round-trip).
_ENQUEUE_TIMEOUT_SECONDS = 3.0


async def get_redis_pool():
    """Get or create the arq Redis pool."""
    return await create_pool(redis_settings, default_queue_name=settings.APP_DOMAIN)


async def enqueue_task(task_name: str, *args, **kwargs):
    """Enqueue a task on the arq worker and return the job."""
    pool = await get_redis_pool()
    try:
        return await pool.enqueue_job(task_name, *args, **kwargs)
    finally:
        await pool.aclose()


async def enqueue_send_notification(
    *,
    user_id: str | None,
    organization_id: str | None,
    notification_type: str,
    title: str,
    message: str | None = None,
    data: dict | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
):
    """Enqueue a notification for delivery via the worker's channels.

    Bounded by :data:`_ENQUEUE_TIMEOUT_SECONDS` so a hung Redis never stalls the
    request path; callers (the ``notify_*`` helpers) already run inside a
    ``try/except`` that swallows failures.
    """
    return await asyncio.wait_for(
        enqueue_task(
            "task_send_notification",
            user_id=user_id,
            organization_id=organization_id,
            notification_type=str(notification_type),
            title=title,
            message=message,
            data=data,
            reference_type=reference_type,
            reference_id=reference_id,
        ),
        timeout=_ENQUEUE_TIMEOUT_SECONDS,
    )


async def enqueue_drip_event(*, event: str, email: str, payload: dict):
    """Enqueue a Resend automation event (see ``app.services.drip``).

    Bounded like :func:`enqueue_send_notification` so a hung Redis never stalls
    the request path; the calling helper already swallows failures.
    """
    return await asyncio.wait_for(
        enqueue_task(
            "task_fire_drip_event",
            event=event,
            email=email,
            payload=payload,
        ),
        timeout=_ENQUEUE_TIMEOUT_SECONDS,
    )


# ===== Misc tasks =====


async def enqueue_task_ping():
    """Enqueue a simple ping task for testing."""
    return await enqueue_task("task_ping")


async def task_ping(ctx: dict) -> str:
    """Worker function for the ``task_ping`` job."""
    logger.info("task_ping executed")
    return "pong"


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
