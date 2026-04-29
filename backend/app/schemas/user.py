from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    id: str
    email: str
    name: str | None = None
    picture: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    picture: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
