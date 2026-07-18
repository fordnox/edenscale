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
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import DocumentType, UserRole
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.document import DocumentCreate
from app.schemas.email_ingest import EmailIngestRequest, EmailIngestResult
from app.services.notifications import notify_document_uploaded
from app.services.storage import get_storage, key_from_file_url
from app.tasks import enqueue_draft_letter

logger = logging.getLogger(__name__)

# Only these roles may attach documents to an org (matches the documents router).
_INGEST_ROLES = frozenset({UserRole.admin, UserRole.fund_manager})
# Mirror the 100 MB ceiling enforced by PUT /documents/upload/{key}.
_MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024


def _safe_name(file_name: str) -> str:
    """Sanitize an attachment filename into a storage-key-safe segment."""
    safe = file_name.strip().replace("/", "_") or "attachment.bin"
    return safe[:255]


def _is_pdf(mime_type: str | None, file_name: str) -> bool:
    """Whether an attachment is a PDF, by declared mime type or extension."""
    mime = (mime_type or "").split(";", 1)[0].strip().lower()
    return mime == "application/pdf" or file_name.lower().endswith(".pdf")


def _parse_org_tag(recipient: str | None) -> str | None:
    """Extract the ``+<org-slug>`` sub-address tag from an envelope recipient.

    ``ingest+acme@newtaven.com`` → ``"acme"``; ``ingest@newtaven.com`` → ``None``.
    Tolerates a display-name form (``"Name" <ingest+acme@...>``) and normalizes to
    lowercase so it matches ``Organization.slug``.
    """
    if not recipient:
        return None
    address = recipient.strip()
    if "<" in address and ">" in address:
        address = address[address.rfind("<") + 1 : address.rfind(">")]
    local = address.split("@", 1)[0]
    if "+" not in local:
        return None
    tag = local.split("+", 1)[1].strip().lower()
    return tag or None


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

        # 2. Resolve the target organization (see _resolve_organization).
        organization_id, reason = self._resolve_organization(user, payload.recipient)
        if organization_id is None:
            return self._drop(reason or "could not resolve organization")

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
                    organization_id=organization_id,
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

            # Auto-draft a letter from an emailed PDF (when the feature is on).
            # Best-effort: a queue hiccup must not fail an ingest whose document
            # is already stored — the draft is a follow-on convenience.
            if settings.letter_drafting_enabled and _is_pdf(
                attachment.mime_type, safe_name
            ):
                try:
                    await enqueue_draft_letter(
                        document_id=str(document.id), user_id=str(user.id)
                    )
                except Exception:
                    logger.exception(
                        "email-ingest: failed to enqueue letter draft for "
                        "document %s",
                        document.id,
                    )

        if not created:
            return self._drop("no storable attachments")
        return EmailIngestResult(status="created", document_ids=created)

    def _resolve_organization(
        self, user: User, recipient: str | None
    ) -> tuple[uuid.UUID | None, str | None]:
        """Pick the target org for an ingest, returning ``(org_id, drop_reason)``.

        A ``+<org-slug>`` tag on the recipient selects the org explicitly; the
        sender must hold an eligible (admin/fund_manager) membership there, or
        the mail is dropped — an invalid tag never silently falls back to
        another org. Without a tag, a sender with exactly one eligible
        membership resolves to it; zero or several is ambiguous, so drop and
        (for the multi-org case) tell them to use the tagged address.
        """
        tag = _parse_org_tag(recipient)
        if tag is not None:
            org = OrganizationRepository(self.db).get_by_slug(tag)
            if org is None:
                return None, f"unknown organization tag {tag!r}"
            membership = self.memberships.get(user.id, org.id)  # type: ignore[invalid-argument-type]
            if membership is None or membership.role not in _INGEST_ROLES:
                return None, (
                    f"sender {user.email!r} is not authorized for organization "
                    f"{tag!r}"
                )
            return org.id, None  # type: ignore[invalid-return-type]

        eligible = [
            m
            for m in self.memberships.list_for_user(user.id)  # type: ignore[invalid-argument-type]
            if m.role in _INGEST_ROLES
        ]
        if len(eligible) == 1:
            return eligible[0].organization_id, None  # type: ignore[invalid-return-type]
        if not eligible:
            return None, f"sender {user.email!r} has no eligible memberships"
        return None, (
            f"sender {user.email!r} belongs to {len(eligible)} organizations; "
            "target one with ingest+<org-slug>@newtaven.com"
        )

    def _drop(self, reason: str) -> EmailIngestResult:
        logger.info("email-ingest drop: %s", reason)
        return EmailIngestResult(status="dropped", reason=reason)
