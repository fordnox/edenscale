import uuid

from sqlalchemy import JSON, Column, DateTime, String, Uuid, func

from app.core.database import Base


class EmailIngestMessage(Base):
    """Idempotency record for a successfully processed inbound email.

    One row per ``message_id`` (see ``EmailIngestRequest.message_id``) that
    produced at least one ``Document``, recording the resulting document ids
    so a retried delivery of the same message -- the Cloudflare Worker retries
    on any non-2xx response, and mail delivery is at-least-once in general --
    returns the original result instead of re-creating documents, re-notifying
    managers, or re-enqueuing letter drafts.

    ``message_id`` is optional at the API layer: the Worker does not send it
    yet, so most ingests never get a row here and are processed exactly as
    before this table existed -- dedupe only engages once the Worker starts
    sending it. A "dropped" ingest (unknown/ambiguous sender, nothing
    storable) never writes a row either: a drop has no side effect to guard
    against, so a retried drop is naturally idempotent on its own.
    """

    __tablename__ = "email_ingest_messages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(String(998), nullable=False, unique=True, index=True)
    document_ids = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, server_default=func.now())
