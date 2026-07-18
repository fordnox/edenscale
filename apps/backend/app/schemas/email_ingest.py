from pydantic import UUID4, BaseModel, Field


class EmailIngestAttachment(BaseModel):
    file_name: str = Field(min_length=1, max_length=1024)
    mime_type: str | None = Field(default=None, max_length=100)
    # Base64-encoded attachment bytes (the Worker parses with
    # ``attachmentEncoding: "base64"``).
    content_base64: str = Field(min_length=1)


class EmailIngestRequest(BaseModel):
    # The SMTP envelope sender, as forwarded by the Worker. Resolved against
    # ``users.email`` to determine the target organization.
    sender_email: str = Field(min_length=3, max_length=320)
    subject: str = Field(default="", max_length=998)
    attachments: list[EmailIngestAttachment] = Field(min_length=1)


class EmailIngestResult(BaseModel):
    # "created" when at least one document was stored; "dropped" otherwise
    # (unknown/ambiguous sender, or nothing storable). A drop is not an error —
    # the Worker just logs the reason.
    status: str
    reason: str | None = None
    document_ids: list[UUID4] = Field(default_factory=list)
