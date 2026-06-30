from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, EmailStr, Field


class InvestorContactCreate(BaseModel):
    user_id: UUID4 | None = None
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=150)
    is_primary: bool | None = False


class InvestorContactUpdate(BaseModel):
    user_id: UUID4 | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=150)
    is_primary: bool | None = None


class InvestorContactRead(BaseModel):
    id: UUID4
    investor_id: UUID4
    user_id: UUID4 | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    title: str | None
    is_primary: bool | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
