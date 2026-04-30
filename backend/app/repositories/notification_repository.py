from datetime import datetime, timezone

from sqlalchemy.orm import Query, Session

from app.models.enums import NotificationStatus
from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Notification)

    def list_for_user(
        self,
        user_id: int,
        *,
        status: NotificationStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        query = self._base_query().filter(Notification.user_id == user_id)
        if status is not None:
            query = query.filter(Notification.status == status)
        return (
            query.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get(self, notification_id: int) -> Notification | None:
        return self._base_query().filter(Notification.id == notification_id).first()

    def create(
        self,
        *,
        user_id: int,
        title: str,
        message: str,
        related_type: str | None = None,
        related_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            related_type=related_type,
            related_id=related_id,
            status=NotificationStatus.unread,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_read(self, notification_id: int) -> Notification | None:
        notification = self.get(notification_id)
        if notification is None:
            return None
        if notification.status is NotificationStatus.unread:
            notification.status = NotificationStatus.read
            notification.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_archived(self, notification_id: int) -> Notification | None:
        notification = self.get(notification_id)
        if notification is None:
            return None
        if notification.status is not NotificationStatus.archived:
            notification.status = NotificationStatus.archived
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_read(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.status == NotificationStatus.unread,
            )
            .update(
                {
                    Notification.status: NotificationStatus.read,
                    Notification.read_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated)
