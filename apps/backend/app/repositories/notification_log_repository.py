import uuid

from sqlalchemy.orm import Session

from app.models.notification_log import NotificationLog

# Statuses that mean "this channel does not need to be attempted again" — a
# terminal outcome for this delivery key. ``failed`` is deliberately excluded:
# it means the attempt did not complete, so a retry should try again rather
# than skip it forever.
DELIVERED_STATUSES = {"sent", "skipped"}


class NotificationLogRepository:
    """Read/write access to the per-channel delivery audit trail.

    The unique key for one delivery is
    ``(notification_type, reference_type, reference_id, channel, recipient)``
    — see ``NotificationLog`` for why the reference columns use an ``""``
    sentinel instead of ``NULL``. This repository is what lets a retried arq
    job recognise work already done instead of re-sending it.
    """

    def __init__(self, db: Session):
        self.db = db

    def find_delivery(
        self,
        *,
        notification_type: str,
        reference_type: str,
        reference_id: str,
        channel: str,
        recipient: str,
    ) -> NotificationLog | None:
        return (
            self.db.query(NotificationLog)
            .filter(
                NotificationLog.notification_type == notification_type,
                NotificationLog.reference_type == reference_type,
                NotificationLog.reference_id == reference_id,
                NotificationLog.channel == channel,
                NotificationLog.recipient == recipient,
            )
            .first()
        )

    def is_delivered(
        self,
        *,
        notification_type: str,
        reference_type: str,
        reference_id: str,
        channel: str,
        recipient: str,
    ) -> bool:
        """Has this (type, reference, channel, recipient) already gone out?

        ``failed`` attempts do not count — they are exactly the case a retry
        exists to correct.
        """
        existing = self.find_delivery(
            notification_type=notification_type,
            reference_type=reference_type,
            reference_id=reference_id,
            channel=channel,
            recipient=recipient,
        )
        return existing is not None and existing.status in DELIVERED_STATUSES

    def record_delivery(
        self,
        *,
        notification_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        organization_id: uuid.UUID | None,
        notification_type: str,
        reference_type: str,
        reference_id: str,
        channel: str,
        recipient: str,
        subject: str | None,
        status: str,
        provider_response: dict | None,
        error_message: str | None,
    ) -> NotificationLog:
        """Create or update the delivery row for this key, and commit it now.

        Committing immediately (rather than batching with the caller's next
        channel) is what makes the idempotency check durable: if the process
        dies right after this call returns, the next attempt sees this
        delivery's real status instead of redoing work that already happened.
        Update-in-place (rather than insert-only) is required because the
        unique constraint allows only one row per key — a ``failed`` attempt
        followed by a successful retry must become one ``sent`` row, not a
        second insert that would violate the constraint.
        """
        existing = self.find_delivery(
            notification_type=notification_type,
            reference_type=reference_type,
            reference_id=reference_id,
            channel=channel,
            recipient=recipient,
        )
        if existing is not None:
            existing.notification_id = notification_id
            existing.user_id = user_id
            existing.organization_id = organization_id
            existing.subject = subject
            existing.status = status
            existing.provider_response = provider_response
            existing.error_message = error_message
            log = existing
        else:
            log = NotificationLog(
                notification_id=notification_id,
                user_id=user_id,
                organization_id=organization_id,
                notification_type=notification_type,
                reference_type=reference_type,
                reference_id=reference_id,
                channel=channel,
                recipient=recipient,
                subject=subject,
                status=status,
                provider_response=provider_response,
                error_message=error_message,
            )
            self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
