from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationStatus


class NotificationRead(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    status: NotificationStatus
    related_type: str | None
    related_id: int | None
    read_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationsReadAllResponse(BaseModel):
    updated: int
