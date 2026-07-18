# Backend Email-Ingest Endpoint — Implementation Plan

Companion to `PLAN.md`. This is the backend side the Worker POSTs to: a
shared-secret endpoint that resolves the sender's organization and stores each
email attachment as a `Document`.

All paths below are under `apps/backend/app/`.

## Decisions (fixed)
- Auth = **shared-secret header** `X-Email-Ingest-Token` vs `settings.EMAIL_INGEST_TOKEN`
  (mirrors the existing `x-dev-storage-token` / `DEV_STORAGE_TOKEN` precedent in
  `routers/documents.py`). No Hanko JWT — the caller is a machine.
- Sender resolution = **by email** → `User` → exactly one `admin`/`fund_manager`
  membership → that org. Zero / ambiguous / LP-only / unknown ⇒ **drop** (200 with
  `status: "dropped"`, no exception, no document).
- Reuses the existing storage service and `DocumentRepository` — no new storage code.

## 1. Config — `core/config.py`

Add one setting alongside the other storage/token settings (near
`DEV_STORAGE_TOKEN`, config.py:31-40):

```python
EMAIL_INGEST_TOKEN: str = ""   # empty ⇒ feature disabled (endpoint returns 404)
```

Empty default keeps the feature off until an operator sets the secret in the
backend env (Kamal / 1Password), matching how `RESEND_API_KEY` gates email.

## 2. Schemas — `schemas/email_ingest.py` (new)

```python
from pydantic import BaseModel, Field, EmailStr

class EmailIngestAttachment(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    content_base64: str = Field(min_length=1)

class EmailIngestRequest(BaseModel):
    sender_email: EmailStr
    subject: str = Field(default="", max_length=255)
    attachments: list[EmailIngestAttachment] = Field(min_length=1)

class EmailIngestResult(BaseModel):
    status: str                 # "created" | "dropped"
    reason: str | None = None   # populated when dropped
    document_ids: list[UUID4] = []
```

Export these from `schemas/__init__.py` (coding rule: keep `__init__` in sync).

## 3. Service — `services/email_ingest.py` (new, repository pattern)

Single entry point; all DB access via repositories, storage via `get_storage()`.

```python
import base64, secrets
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories import UserRepository, UserOrganizationMembershipRepository, DocumentRepository
from app.schemas import DocumentCreate, EmailIngestRequest, EmailIngestResult
from app.services.storage import get_storage
from app.services.notifications import notify_document_uploaded
from app.models.enums import DocumentType, UserRole

_INGEST_ROLES = {UserRole.admin, UserRole.fund_manager}
_MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024  # match documents router ceiling

class EmailIngestService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.memberships = UserOrganizationMembershipRepository(db)
        self.documents = DocumentRepository(db)

    def ingest(self, payload: EmailIngestRequest) -> EmailIngestResult:
        # 1. Resolve sender → User
        user = self.users.get_by_email(payload.sender_email)
        if user is None:
            return _drop(f"unknown sender {payload.sender_email}")

        # 2. Require exactly one admin/fund_manager membership
        memberships = [m for m in self.memberships.list_for_user(user.id)
                       if m.role in _INGEST_ROLES]
        if len(memberships) != 1:
            return _drop(f"sender has {len(memberships)} eligible memberships")
        org_id = memberships[0].organization_id

        # 3. Store each attachment + create Document
        storage = get_storage()
        created = []
        for att in payload.attachments:
            raw = base64.b64decode(att.content_base64)
            if len(raw) > _MAX_ATTACHMENT_BYTES:
                continue  # skip oversized; logged by caller via result
            safe = _safe_name(att.file_name)
            key = f"documents/{secrets.token_urlsafe(16)}/{safe}"
            storage.write(key, raw, att.mime_type or "application/octet-stream")
            file_url = storage.file_url_for_key(key)   # see note below
            doc = self.documents.create(
                DocumentCreate(
                    organization_id=org_id,
                    document_type=DocumentType.other,
                    title=(payload.subject or att.file_name)[:255],
                    file_name=safe,
                    file_url=file_url,
                    mime_type=att.mime_type,
                    file_size=len(raw),
                    is_confidential=True,
                ),
                uploaded_by_user_id=user.id,
            )
            notify_document_uploaded(self.db, doc)   # same helper the router calls
            created.append(doc.id)

        if not created:
            return _drop("no storable attachments")
        return EmailIngestResult(status="created", document_ids=created)
```

`_drop(reason)` → `EmailIngestResult(status="dropped", reason=reason)`.
`_safe_name` = the same sanitizer used by `routers/documents.py` upload-init
(factor it into a shared util if not already importable).

### Storage note — deriving `file_url` from a key
`documents.py` gets `file_url` from `storage.presign_put(...)` (which also returns
an upload URL the browser uses). Here the server writes bytes itself, so it only
needs the **canonical** `file_url`. Two clean options, decide during impl:
- (a) call `storage.presign_put(key, mime_type)` and use only its `file_url`
  field (ignore `upload_url`) — zero new storage code; or
- (b) add a small `file_url_for_key(key)` method to `StoragePort` /
  `LocalDevStorage` / `S3Storage` that returns just the canonical URL.

Recommend **(a)** first (no `StoragePort` change); refactor to (b) only if the
presign call has unwanted side effects. Verify `presign_put` is side-effect-free
(it builds URLs; S3 presign is a local signing op — safe).

## 4. Router — `routers/email_ingest.py` (new)

Mounted like `dev_storage_router` — at the app root in `main.py`, **not** behind
`get_current_user`.

```python
import hmac
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.schemas import EmailIngestRequest, EmailIngestResult
from app.services.email_ingest import EmailIngestService

router = APIRouter(prefix="/email-ingest", tags=["email-ingest"])

def _require_ingest_token(x_email_ingest_token: str = Header(default="")):
    if not settings.EMAIL_INGEST_TOKEN:
        raise HTTPException(status.HTTP_404_NOT_FOUND)          # feature disabled
    if not hmac.compare_digest(x_email_ingest_token, settings.EMAIL_INGEST_TOKEN):
        raise HTTPException(status.HTTP_403_FORBIDDEN)

@router.post("/documents", response_model=EmailIngestResult,
             dependencies=[Depends(_require_ingest_token)])
def ingest_documents(payload: EmailIngestRequest, db: Session = Depends(get_db)):
    return EmailIngestService(db).ingest(payload)
```

- Returns **200** for both created and dropped (drop is not an error; the Worker
  logs it). Only auth failures are non-2xx.
- `hmac.compare_digest` = constant-time comparison.

### `main.py` wiring
Add next to the dev-storage mount (main.py:151-154):
```python
from app.routers import email_ingest_router
app.include_router(email_ingest_router)
```

## 5. `__init__.py` updates (coding rule)
- `schemas/__init__.py` — export the three schemas.
- `services/__init__.py` — export `EmailIngestService`.
- `routers/__init__.py` — export `email_ingest_router` (alias `router`).

## 6. Tests — `tests/test_email_ingest.py`
- **feature disabled**: `EMAIL_INGEST_TOKEN=""` ⇒ `POST /email-ingest/documents` → 404.
- **bad token** ⇒ 403.
- **unknown sender** ⇒ 200 `{status: "dropped", reason: "unknown sender ..."}`, no rows.
- **ambiguous membership** (user with 2 admin orgs) ⇒ 200 dropped.
- **happy path**: seed a user with one `admin` membership, POST one base64 PDF ⇒
  200 `{status: "created", document_ids:[...]}`; assert a `Document` row exists
  with `organization_id`, `uploaded_by_user_id`, `document_type=other`,
  `is_confidential=True`, and that the blob was written (local storage backend).
- **oversized attachment** skipped ⇒ dropped when it's the only one.

Use the existing test fixtures/DB setup; set `EMAIL_INGEST_TOKEN` via monkeypatch
on `settings` (or env) per how other tests toggle config.

## 7. Contract sync
Run `make openapi` after the router lands so `openapi.json` +
`packages/api/src/schema.d.ts` include the new endpoint (pre-commit rule 3).
Frontends don't call it, but the schema must stay complete.

## 8. Pre-commit checklist
1. `make test` (incl. new `test_email_ingest.py`).
2. `make lint`.
3. `make openapi`.

## Out of scope for v1
- Plus-addressing / fund/investor targeting (org-only).
- Storing the email body as a document.
- Dedup of repeated sends.
- Rate limiting (the shared secret + Cloudflare fronting is the v1 boundary).
```
