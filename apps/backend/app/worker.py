import logging

from arq import cron

from app.core.config import settings
from app.tasks import (
    cron_mark_overdue_capital_calls,
    redis_settings,
    task_ping,
    task_send_capital_call_emails,
    task_send_distribution_emails,
    task_send_document_email,
    task_send_invitation_email,
    task_send_welcome_email,
)

logger = logging.getLogger(__name__)


class WorkerSettings:
    queue_name = settings.APP_DOMAIN
    functions = [
        task_ping,
        task_send_invitation_email,
        task_send_capital_call_emails,
        task_send_distribution_emails,
        task_send_welcome_email,
        task_send_document_email,
    ]
    cron_jobs = [
        cron(cron_mark_overdue_capital_calls, hour=6, minute=0)  # type: ignore[invalid-argument-type]
    ]
    redis_settings = redis_settings
