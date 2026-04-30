"""Helper for emitting in-app notifications from business-event sites.

Centralises the call into ``NotificationRepository.create`` so each callsite
remains a single line and resilient to schema changes. Notifications are
fire-and-forget side effects: callers should never let a notification failure
break the underlying business operation, so this helper swallows errors after
rolling back its own pending writes.
"""

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository


def notify(
    db: Session,
    *,
    user_id: int | None,
    title: str,
    message: str,
    related_type: str | None = None,
    related_id: int | None = None,
) -> Notification | None:
    """Persist one notification row for ``user_id``.

    Silently no-ops when ``user_id`` is None so ambiguous fan-outs (e.g. a
    communication recipient with no linked user) don't have to special-case the
    call site.
    """
    if user_id is None:
        return None
    repo = NotificationRepository(db)
    return repo.create(
        user_id=user_id,
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id,
    )
