from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict

from app.models.enums import NotificationStatus


class NotificationRead(BaseModel):
    id: UUID4
    user_id: UUID4
    title: str
    message: str
    status: NotificationStatus
    related_type: str | None
    related_id: UUID4 | None
    read_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationsReadAllResponse(BaseModel):
    updated: int
