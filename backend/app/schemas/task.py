from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskStatus


class TaskCreate(BaseModel):
    fund_id: int | None = None
    assigned_to_user_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = TaskStatus.open
    due_date: date | None = None


class TaskUpdate(BaseModel):
    fund_id: int | None = None
    assigned_to_user_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    id: int
    fund_id: int | None
    assigned_to_user_id: int | None
    created_by_user_id: int | None
    title: str
    description: str | None
    status: TaskStatus
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
