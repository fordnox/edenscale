import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class NotificationLog(Base):
    """Per-channel delivery audit for every notification the worker sends.

    One row per (notification_type, reference_type, reference_id, channel,
    recipient) delivery — enforced by a unique constraint so a retried arq job
    can recognise "already delivered" and skip re-sending a channel that
    already went out, instead of double-emailing the recipient.

    ``reference_type`` / ``reference_id`` identify the domain object the
    notification is about (e.g. ``("capital_call", <uuid>)``). Some
    notification types have no natural reference; those columns are
    non-nullable with an ``""`` sentinel rather than ``NULL`` specifically so
    the unique constraint still dedupes them — PostgreSQL treats every ``NULL``
    as distinct in a unique constraint, so a nullable pair would silently stop
    deduping exactly the rows that have no reference, which is the opposite of
    what an idempotency key is for.

    ``user_id`` is nullable so email-only deliveries to a recipient with no
    user account (e.g. an invitation to a not-yet-registered address) can
    still be logged.
    """

    __tablename__ = "notification_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(
        Uuid(as_uuid=True), ForeignKey("notifications.id"), nullable=True
    )
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    notification_type = Column(String(255), nullable=False)
    reference_type = Column(String(100), nullable=False, server_default="")
    reference_id = Column(String(255), nullable=False, server_default="")
    channel = Column(String(20), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False)
    provider_response = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    notification = relationship("Notification", foreign_keys=[notification_id])
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])

    __table_args__ = (
        Index("ix_notification_logs_user_id", "user_id"),
        Index("ix_notification_logs_notification_type", "notification_type"),
        Index("ix_notification_logs_channel", "channel"),
        Index("ix_notification_logs_status", "status"),
        Index("ix_notification_logs_created_at", "created_at"),
        UniqueConstraint(
            "notification_type",
            "reference_type",
            "reference_id",
            "channel",
            "recipient",
            name="uq_notification_logs_delivery",
        ),
    )
