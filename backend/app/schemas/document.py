from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentType


class DocumentCreate(BaseModel):
    organization_id: int | None = None
    fund_id: int | None = None
    investor_id: int | None = None
    document_type: DocumentType
    title: str = Field(min_length=1, max_length=255)
    file_name: str = Field(min_length=1, max_length=255)
    file_url: str = Field(min_length=1)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = None
    is_confidential: bool = True


class DocumentUpdate(BaseModel):
    organization_id: int | None = None
    fund_id: int | None = None
    investor_id: int | None = None
    document_type: DocumentType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = None
    is_confidential: bool | None = None


class DocumentRead(BaseModel):
    id: int
    organization_id: int | None
    fund_id: int | None
    investor_id: int | None
    uploaded_by_user_id: int | None
    document_type: DocumentType
    title: str
    file_name: str
    file_url: str
    download_url: str | None = None
    mime_type: str | None
    file_size: int | None
    is_confidential: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadInit(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None, ge=0)


class DocumentUploadInitResponse(BaseModel):
    upload_url: str
    file_url: str
    expires_at: datetime
