from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CommunicationType


class CommunicationRecipientRef(BaseModel):
    """Optional override for who should receive a communication.

    Either `user_id` or `investor_contact_id` must be set; recipients with both
    populated are allowed and treated as a single row keyed on (user, contact).
    """

    user_id: UUID4 | None = None
    investor_contact_id: UUID4 | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "CommunicationRecipientRef":
        if self.user_id is None and self.investor_contact_id is None:
            raise ValueError("recipient must set user_id or investor_contact_id")
        return self


class CommunicationCreate(BaseModel):
    fund_id: UUID4 | None = None
    type: CommunicationType
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class CommunicationUpdate(BaseModel):
    fund_id: UUID4 | None = None
    type: CommunicationType | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1)


class CommunicationSendRequest(BaseModel):
    recipients: list[CommunicationRecipientRef] = Field(default_factory=list)


class CommunicationRecipientRead(BaseModel):
    id: UUID4
    communication_id: UUID4
    user_id: UUID4 | None
    investor_contact_id: UUID4 | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class CommunicationRead(BaseModel):
    id: UUID4
    fund_id: UUID4 | None
    sender_user_id: UUID4 | None
    type: CommunicationType
    subject: str
    body: str
    sent_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    recipients: list[CommunicationRecipientRead]

    model_config = ConfigDict(from_attributes=True)
