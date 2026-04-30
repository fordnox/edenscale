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

The shipped `LocalDevStorage` writes bytes under `backend/dev_storage/<key>` and returns `http://localhost:8000/dev-storage/{key}` for both `upload_url` and `public_url`. A small dev-only route in `app/routers/documents.py::dev_storage_router` serves bytes back. `get_storage()` is a process-wide singleton selected by `settings.STORAGE_BACKEND` (currently only `local`).

Production is a future `S3Storage(StoragePort)` that returns real presigned URLs; nothing else in the codebase changes.

### Option B — proxy uploads through the API

Client `POST`s multipart/form-data to FastAPI; FastAPI streams to S3 with credentials. `documents.file_url` stores an internal redirect URL.

### Option C — couple to boto3 / S3 from day one

Use `boto3` directly in the documents repository. Spin up `localstack` for local dev.

## Decision

**Option A.**

## Consequences

### What we get

- **One upload protocol everywhere.** The frontend always does an `init → PUT bytes → record` flow. Local dev `PUT`s to a FastAPI route; production `PUT`s to S3. The frontend does not branch on environment.
- **Stable canonical URL on the row.** `documents.file_url` is what list endpoints render. The storage backend can rotate signing keys, change region, or add a CDN without touching that column.
- **Trivial onboarding.** A new contributor runs `make sync && make start-backend` and the documents flow works. No object-storage credentials needed.
- **Test isolation is easy.** Tests can swap `_storage_singleton` for a temp-dir `LocalDevStorage` via `reset_storage()`. There's no boto3 mock surface to maintain.
- **A clear seam for a future migration.** Implementing `S3Storage(StoragePort)` is the only change required to go from local to cloud. No documents router or repository code moves.

### What we accept

- **`LocalDevStorage` is unauthenticated.** Anyone who can reach `localhost:8000/dev-storage/{key}` can read any uploaded file. Acceptable for a dev box; explicitly **not** suitable for production. We document this in the docstring and gate it on `STORAGE_BACKEND=local`.
- **Two singletons of indirection.** `get_storage()` returns the cached implementation; tests must call `reset_storage()` between cases that swap the backend. We accept this complexity because the alternative (passing storage into every repository constructor) is noisier.
- **Presigned-URL TTL is a fixed 15 minutes.** Hard-coded in `_PRESIGN_TTL`. Production backends can choose to honour it or not (`LocalDevStorage` ignores it and serves bytes whenever the dev route is hit). If we ever need short-lived links, we'll thread the TTL through the call site.
- **`file_url` and storage key are coupled by string parsing.** `key_from_file_url(...)` extracts the key from the URL. If we change URL shape, we'll break old rows unless we migrate them. Today we accept this because the URL format is stable per backend.

### Why we did not pick Option B (proxy uploads)

- **Doubles the bytes through our API.** Every upload hits the FastAPI process, then S3. Capital-call PDFs and quarterly reports can be tens of MB; this is a needless bandwidth and latency tax.
- **Couples the API process to the upload's duration.** A slow client holds an API worker for the length of the upload — a denial-of-service risk we'd rather not own.

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

- We deploy to production. Implement `S3Storage(StoragePort)` (or `R2Storage` / `GCSStorage`) with real presigned URLs and add the relevant credentials to `Settings`.
- We need server-side encryption keys, content-disposition headers, or CDN signing. Extend the port — `presign_put` already accepts `mime_type`; widen the signature there rather than adding a sibling method.
- We need authenticated reads. `presign_get` is the right place to add a short TTL signed URL; callers (frontend list/detail pages) would resolve URLs lazily instead of trusting the stored `file_url`.
