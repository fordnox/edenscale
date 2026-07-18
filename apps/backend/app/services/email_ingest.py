"""Inbound-email → document ingestion.

Backs ``POST /email-ingest/documents``. Given a sender email and a set of
attachments (from the Cloudflare email-ingest Worker), resolve the sender's
organization and store each attachment as a ``Document``.

Routing is by sender email only: the sender must resolve to a single ``User``
holding exactly one ``admin``/``fund_manager`` membership; that membership's
organization owns the resulting documents. Anything ambiguous (unknown sender,
zero or multiple eligible memberships) is *dropped* — reported back as a
``status="dropped"`` result rather than raised, so the Worker can log it and
move on. Storage reuses the same ``presign_put`` → ``write`` path as the
browser upload flow, so ``S3_PREFIX`` handling stays identical.
"""

import base64
import binascii
import logging
import secrets

from sqlalchemy.orm import Session

from app.models.enums import DocumentType, UserRole
from app.repositories.document_repository import DocumentRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.document import DocumentCreate
from app.schemas.email_ingest import EmailIngestRequest, EmailIngestResult
from app.services.notifications import notify_document_uploaded
from app.services.storage import get_storage, key_from_file_url

logger = logging.getLogger(__name__)

# Only these roles may attach documents to an org (matches the documents router).
_INGEST_ROLES = frozenset({UserRole.admin, UserRole.fund_manager})
# Mirror the 100 MB ceiling enforced by PUT /documents/upload/{key}.
_MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024


def _safe_name(file_name: str) -> str:
    """Sanitize an attachment filename into a storage-key-safe segment."""
    safe = file_name.strip().replace("/", "_") or "attachment.bin"
    return safe[:255]


class EmailIngestService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.memberships = UserOrganizationMembershipRepository(db)
        self.documents = DocumentRepository(db)

    async def ingest(self, payload: EmailIngestRequest) -> EmailIngestResult:
        # 1. Resolve the sender to a local user (case-insensitive on email).
        user = self.users.get_by_email(payload.sender_email)
        if user is None:
            normalized = payload.sender_email.strip().lower()
            if normalized != payload.sender_email:
                user = self.users.get_by_email(normalized)
        if user is None:
            return self._drop(f"unknown sender {payload.sender_email!r}")

        # 2. Require exactly one admin/fund_manager membership.
        eligible = [
            m
            for m in self.memberships.list_for_user(user.id)  # type: ignore[invalid-argument-type]
            if m.role in _INGEST_ROLES
        ]
        if len(eligible) != 1:
            return self._drop(
                f"sender {payload.sender_email!r} has {len(eligible)} eligible "
                "memberships (need exactly 1)"
            )
        organization_id = eligible[0].organization_id

        # 3. Store each attachment and create a Document row.
        storage = get_storage()
        created: list = []
        for attachment in payload.attachments:
            try:
                raw = base64.b64decode(attachment.content_base64, validate=True)
            except (binascii.Error, ValueError):
                logger.warning(
                    "email-ingest: skipping %r with undecodable base64 content",
                    attachment.file_name,
                )
                continue
            if not raw or len(raw) > _MAX_ATTACHMENT_BYTES:
                logger.warning(
                    "email-ingest: skipping %r (%d bytes, limit %d)",
                    attachment.file_name,
                    len(raw),
                    _MAX_ATTACHMENT_BYTES,
                )
                continue

            safe_name = _safe_name(attachment.file_name)
            logical_key = f"documents/{secrets.token_urlsafe(16)}/{safe_name}"
            # presign_put applies S3_PREFIX and returns the canonical file_url;
            # key_from_file_url recovers the full (prefixed) key that write()
            # expects — exactly the browser upload path, minus the round-trip.
            _, file_url, _ = storage.presign_put(logical_key, attachment.mime_type)
            storage.write(key_from_file_url(file_url), raw, attachment.mime_type)

            title = (payload.subject.strip() or safe_name)[:255]
            document = self.documents.create(
                DocumentCreate(
                    organization_id=organization_id,  # type: ignore[invalid-argument-type]
                    document_type=DocumentType.other,
                    title=title,
                    file_name=safe_name,
                    file_url=file_url,
                    mime_type=attachment.mime_type,
                    file_size=len(raw),
                    is_confidential=True,
                ),
                uploaded_by_user_id=user.id,  # type: ignore[invalid-argument-type]
            )
            await notify_document_uploaded(self.db, document=document)
            created.append(document.id)

        if not created:
            return self._drop("no storable attachments")
        return EmailIngestResult(status="created", document_ids=created)

    def _drop(self, reason: str) -> EmailIngestResult:
        logger.info("email-ingest drop: %s", reason)
        return EmailIngestResult(status="dropped", reason=reason)
