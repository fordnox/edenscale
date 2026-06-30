import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import NotificationStatus


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(
        Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.unread,
    )
    related_type = Column(String(100), nullable=True)
    related_id = Column(Uuid(as_uuid=True), nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="notifications")
