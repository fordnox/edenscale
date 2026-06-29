import logging

from app.core.config import settings
from app.tasks import redis_settings

logger = logging.getLogger(__name__)


class WorkerSettings:
    queue_name = settings.APP_DOMAIN
    functions = []
    cron_jobs = []
    redis_settings = redis_settings
