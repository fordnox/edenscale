---
type: analysis
title: 'ADR-002: StoragePort abstraction with LocalDevStorage default'
created: 2026-04-29
tags:
  - storage
  - documents
  - decision
related:
  - '[[System-Overview]]'
  - '[[Database-Schema]]'
  - '[[ADR-001-RBAC-Via-Hanko-JWT]]'
---

# ADR-002: StoragePort abstraction with LocalDevStorage default

**Status:** Accepted (locked in during the documents milestone)
**Deciders:** Backend team
**Supersedes:** none

## Context

EdenScale's documents flow needs to:

- Accept uploads from the SPA without proxying bytes through the API server.
- Persist a canonical, dereferenceable URL on `documents.file_url` so list endpoints don't need to reach into the blob layer to render a row.
- Work end-to-end on a developer's laptop with no AWS / GCP credentials configured.
- Be swappable to S3 / GCS / R2 in production without touching the documents router or the repositories.

Three shapes were considered.

## Options considered

### Option A — `StoragePort` ABC + `LocalDevStorage` default (chosen)

A small ABC in [`backend/app/services/storage.py`](../../backend/app/services/storage.py):

```python
class StoragePort(ABC):
    @abstractmethod
    def presign_put(self, key, mime_type=None) -> tuple[str, str, datetime]:
        """Return (upload_url, public_url, expires_at)."""

    @abstractmethod
    def presign_get(self, key) -> str:
        """Return a (possibly time-limited) URL the client can GET."""
```

The shipped `LocalDevStorage` writes bytes under `APP_DATA_PATH/dev_storage/<key>` and returns `http://localhost:8000/dev-storage/{key}` for both `upload_url` and `public_url`. A small dev-only route in `app/routers/documents.py::dev_storage_router` serves bytes back. `get_storage()` is a process-wide singleton selected by `settings.STORAGE_BACKEND` (`local` or `s3`).

Production runs `S3Storage(StoragePort)` — see Consequences below; it shipped and nothing else in the codebase changed to accommodate it, exactly as this option predicted.

### Option B — proxy uploads through the API

Client `POST`s multipart/form-data to FastAPI; FastAPI streams to S3 with credentials. `documents.file_url` stores an internal redirect URL.

### Option C — couple to boto3 / S3 from day one

Use `boto3` directly in the documents repository. Spin up `localstack` for local dev.

## Decision

**Option A.**

## Consequences

### What we get

- **One upload protocol everywhere.** The frontend always does an `init → PUT bytes → record` flow, whichever backend is active. The frontend does not branch on environment. **Correction (2026-07-21):** for the shipped `S3Storage`, `PUT`s go to an API-relative route (`PUT /documents/upload/{key}` in `app/routers/documents.py:144`), which writes to the bucket server-side — not a direct-to-bucket presigned PUT as originally envisioned here. See the corrected "Why we did not pick Option B" note below; only reads (`presign_get`) are true direct-to-bucket presigned URLs.
- **Stable canonical URL on the row.** `documents.file_url` is what list endpoints render. The storage backend can rotate signing keys, change region, or add a CDN without touching that column.
- **Trivial onboarding.** A new contributor runs `make sync && make start-backend` and the documents flow works. No object-storage credentials needed.
- **Test isolation is easy.** Tests can swap `_storage_singleton` for a temp-dir `LocalDevStorage` via `reset_storage()`. There's no boto3 mock surface to maintain.
- **The migration seam worked as designed — and has shipped.** `S3Storage(StoragePort)` (`apps/backend/app/services/storage.py`, from ~line 120) is implemented, exercised by `apps/backend/tests/test_storage_s3.py`, and is what `config/deploy.yml` runs in production (`STORAGE_BACKEND=s3`). No documents router or repository code moved to add it, confirming the seam.

### What we accept

- **`LocalDevStorage` is unauthenticated.** Anyone who can reach `localhost:8000/dev-storage/{key}` can read any uploaded file. Acceptable for a dev box; explicitly **not** suitable for production. We document this in the docstring and gate it on `STORAGE_BACKEND=local`. This accepted exposure covers **uploaded blobs only** — `LocalDevStorage` serves bytes strictly from under its own `base_dir` (`APP_DATA_PATH/dev_storage`) keyed by the stored `key`; it never resolves paths outside that storage root.
- **Two singletons of indirection.** `get_storage()` returns the cached implementation; tests must call `reset_storage()` between cases that swap the backend. We accept this complexity because the alternative (passing storage into every repository constructor) is noisier.
- **Presigned-URL TTL is a fixed 15 minutes.** Hard-coded in `_PRESIGN_TTL`. Production backends can choose to honour it or not (`LocalDevStorage` ignores it and serves bytes whenever the dev route is hit). If we ever need short-lived links, we'll thread the TTL through the call site.
- **`file_url` and storage key are coupled by string parsing.** `key_from_file_url(...)` extracts the key from the URL. If we change URL shape, we'll break old rows unless we migrate them. Today we accept this because the URL format is stable per backend.

### Why we did not pick Option B (proxy uploads)

- **Doubles the bytes through our API.** Every upload hits the FastAPI process, then S3. Capital-call PDFs and quarterly reports can be tens of MB; this is a needless bandwidth and latency tax.
- **Couples the API process to the upload's duration.** A slow client holds an API worker for the length of the upload — a denial-of-service risk we'd rather not own.

**Correction (2026-07-21):** the shipped `S3Storage` upload path does in fact proxy bytes through the API (`presign_put` returns the API-relative `/documents/upload/{key}`, and that route calls `S3Storage.write`, which does a server-side `put_object`) — the tradeoff this ADR rejected for Option B. The `S3Storage` class docstring (`apps/backend/app/services/storage.py:120-129`) states the rationale that was actually used: proxying avoids needing bucket CORS configuration, and the upload route is governed by the existing bearer-auth dependency rather than a signature. *Downloads* remain true presigned direct-to-bucket GETs (`presign_get`), consumed as plain link navigations. No evidence (code, tests, or commit history) was found for why the upload side later diverged from this ADR's original Option A description instead of triggering a re-decision — flagged as an open question rather than guessed at.

### Why we did not pick Option C (direct boto3)

- **No clean dev story.** `localstack` works but adds a Docker dependency to `make sync` that contributors regularly hit problems with.
- **Storage logic leaks into repositories.** Without an interface, the documents repository ends up importing boto3, and tests have to mock it. The `StoragePort` ABC keeps that surface in one file.

## Implementation pointers

- ABC + default: [`backend/app/services/storage.py`](../../backend/app/services/storage.py).
- Dev byte-serving route: `app/routers/documents.py::dev_storage_router` (mounted in `main.py` without auth — local-only).
- Upload init / record handlers: `app/routers/documents.py`.
- Test reset: `app.services.storage.reset_storage()`.
- Config: `settings.STORAGE_BACKEND` (defaults to `"local"`).

## Revisit when

- **Done.** ~~We deploy to production. Implement `S3Storage(StoragePort)`...~~ — production deploys with `STORAGE_BACKEND=s3` today (`config/deploy.yml`); `S3Storage` is implemented and tested (`apps/backend/tests/test_storage_s3.py`).
- We need server-side encryption keys, content-disposition headers, or CDN signing. Extend the port — `presign_put` already accepts `mime_type`; widen the signature there rather than adding a sibling method.
- We need authenticated reads. `presign_get` is the right place to add a short TTL signed URL; callers (frontend list/detail pages) would resolve URLs lazily instead of trusting the stored `file_url`.
- `STORAGE_BACKEND` currently silently falls back to `"local"` for any unset/blank value and only raises for an unrecognized string (`get_storage()` in `storage.py`). As of this reconciliation (2026-07-21), there is no production-shaped validation that rejects `local` when other production settings (e.g. a non-localhost `APP_DOMAIN`) are present — `apps/backend/app/core/config.py` has no `model_validator` enforcing this. If a future change adds one, update this ADR to describe it.
