from pydantic import UUID4, BaseModel, Field


class EmailIngestAttachment(BaseModel):
    file_name: str = Field(min_length=1, max_length=1024)
    mime_type: str | None = Field(default=None, max_length=100)
    # Base64-encoded attachment bytes (the Worker parses with
    # ``attachmentEncoding: "base64"``).
    content_base64: str = Field(min_length=1)


class EmailIngestRequest(BaseModel):
    # The SMTP envelope sender, as forwarded by the Worker. Resolved against
    # ``users.email`` to identify (and authorize) the person ingesting.
    sender_email: str = Field(min_length=3, max_length=320)
    # The envelope recipient the mail was delivered to, e.g.
    # ``ingest+acme@newtaven.com``. A ``+<org-slug>`` tag, when present, selects the
    # target organization (the sender must be a member of it). Optional: without
    # a tag, a sender with exactly one eligible org still resolves.
    recipient: str | None = Field(default=None, max_length=320)
    subject: str = Field(default="", max_length=998)
    attachments: list[EmailIngestAttachment] = Field(min_length=1)
    # The originating email's Message-ID header, when the Worker forwards it.
    # Optional: the Worker does not send this yet, so most ingests have none
    # and are processed with no dedupe, exactly as before this field existed.
    # When present and this message was already ingested, the prior result is
    # returned rather than re-creating documents, re-notifying, or
    # re-enqueuing letter drafts -- see EmailIngestService.ingest.
    message_id: str | None = Field(default=None, max_length=998)


class EmailIngestResult(BaseModel):
    # "created" when at least one document was stored; "dropped" otherwise
    # (unknown/ambiguous sender, or nothing storable). A drop is not an error —
    # the Worker just logs the reason.
    status: str
    reason: str | None = None
    document_ids: list[UUID4] = Field(default_factory=list)
