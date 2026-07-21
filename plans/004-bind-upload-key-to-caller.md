# Plan 004: Bind upload keys to the caller who was issued them

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/routers/documents.py apps/backend/app/services/storage.py apps/backend/app/core/config.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-green-suite-and-ci.md, plans/002-storage-fail-closed-and-traversal.md
- **Category**: security
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

`PUT /documents/upload/{key:path}` writes the request body to whatever storage
key the caller names. Its only checks are that the caller is *some*
authenticated user and that the key contains no `..`. Nothing verifies that this
key was ever issued to this caller.

Storage keys are not secret from legitimate viewers: `DocumentRead.file_url` is
returned to everyone who can view a document, and `key_from_file_url` shows the
key is trivially recoverable from that URL. So an LP who can legitimately view a
single fund document learns a writable key — and can then overwrite that
object's bytes with anything.

The damage is invisible. The `Document` row (title, size, uploader, timestamps)
is untouched, and no audit-log entry is written for the object itself. A capital
call notice or a subscription agreement can be silently replaced with different
content while every UI surface still shows the original metadata.

Because the S3 backend applies `S3_PREFIX` at upload-init time and the proxy
accepts the already-prefixed key from the client, the prefix is caller-controlled
too — so on a bucket shared with other applications (the default bucket name in
config suggests exactly that), the write primitive reaches outside this app's
prefix.

## Current state

`apps/backend/app/routers/documents.py:44-48` — key generation. Note the key
already contains server-generated randomness, which is what makes the signed
approach below cheap:

```python
def _generate_storage_key(file_name: str) -> str:
    """Build a storage key with a random prefix to avoid collisions."""
    safe_name = file_name.strip().replace("/", "_") or "upload.bin"
    token = secrets.token_urlsafe(16)
    return f"documents/{token}/{safe_name}"
```

`apps/backend/app/routers/documents.py:123-138` — upload-init issues the URL:

```python
async def init_document_upload(
    payload: DocumentUploadInit,
    # Every role may stage an upload — plain authentication is enough.
    current_user: User = Depends(get_current_user_record),
):
    storage = get_storage()
    key = _generate_storage_key(payload.file_name)
    upload_url, file_url, expires_at = storage.presign_put(key, payload.mime_type)
    return DocumentUploadInitResponse(
        upload_url=upload_url, file_url=file_url, expires_at=expires_at
    )
```

`apps/backend/app/routers/documents.py:144-171` — the unguarded write. The
comment at 148-149 states the *intended* contract; nothing enforces it:

```python
@router.put("/upload/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_document_bytes(
    key: str,
    request: Request,
    # Same bar as upload-init: any authenticated user may push bytes for a
    # key that upload-init handed them.
    current_user: User = Depends(get_current_user_record),
):
    ...
    if ".." in key.split("/") or key.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage key"
        )
    body = await request.body()
    if len(body) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 100 MB upload limit",
        )
    storage = get_storage()
    storage.write(key, body, request.headers.get("content-type"))
```

`apps/backend/app/services/storage.py:185-200` — `S3Storage.presign_put`. Its
comment explicitly records the current (flawed) assumption, and **you will need
to update that comment**:

```python
        # The upload URL is API-relative: the client PUTs the bytes to the
        # authenticated /documents/upload/{key} proxy, which writes to the
        # bucket server-side. Expiry is advisory here — the proxy is governed
        # by bearer auth, not by a signature.
        full_key = _prefixed_key(key)
        upload_url = f"/documents/upload/{quote(full_key, safe='/')}"
```

**Other callers of the write path** — these must keep working. They call
`storage.write(...)` directly, server-side, never through the HTTP proxy, so
they are unaffected by a route-level guard:
- `apps/backend/app/services/email_ingest.py:126` (email attachment ingest)
- `apps/backend/app/routers/bank_imports.py:51` (raw statement file save)

Confirm this yourself with `grep -rn 'storage.write' apps/backend/app` before
starting. If any caller reaches the write path via HTTP, STOP.

## The approach

Use a **stateless signed grant**. At upload-init, compute an HMAC over
`(key, user_id, expiry)` using a server secret, and append it to the returned
`upload_url` as a query parameter. The proxy recomputes the HMAC from the path
key, the authenticated caller's id, and the supplied expiry, and rejects on
mismatch or expiry.

This is preferred over a Redis-backed grant table because it adds no new
infrastructure, no new request-path failure mode, and no new latency — and the
key already carries server-generated randomness, so replay within the TTL by the
same user is harmless (it is their own key).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Document tests | `cd apps/backend && uv run pytest tests/test_documents_api.py tests/test_storage_s3.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Import smoke test | `cd apps/backend && uv run python -c "from app import *"` | exit 0 |
| Frontend typecheck | `pnpm turbo run typecheck` | exit 0 |
| Regenerate client | `make openapi` | exit 0, schema.d.ts updated |

## Scope

**In scope**:
- `apps/backend/app/routers/documents.py`
- `apps/backend/app/services/storage.py` (the `presign_put` comment, and only if
  the signature needs threading — prefer keeping signing in the router)
- `apps/backend/app/core/config.py` (add the signing secret setting)
- `apps/backend/tests/test_documents_api.py` (add cases)
- `apps/backend/openapi.json` and `packages/api/src/schema.d.ts` (via `make openapi` only — never hand-edit)

**Out of scope** (do NOT touch):
- The dev-storage routes — plan 002 owns those.
- `apps/backend/app/services/email_ingest.py` and
  `apps/backend/app/routers/bank_imports.py` — they call `storage.write`
  server-side and must **not** need a grant. If your change forces them to
  construct one, you have put the guard in the wrong layer; move it to the route.
- Presigned **GET** / read authorization — a real but separate question.
- Content-type allowlisting on uploads — separate finding, separate plan.

## Git workflow

- Branch: `advisor/004-bind-upload-key`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the signing secret

In `apps/backend/app/core/config.py`, add `UPLOAD_SIGNING_SECRET: str = ""`.

Extend the production validator added by plan 002 (the
`@model_validator(mode="after")` on `Settings`) so a production-shaped
configuration with an empty `UPLOAD_SIGNING_SECRET` fails at startup, exactly as
it does for `STORAGE_BACKEND`. Local development with an empty secret must keep
working — see step 3 for how the route behaves then.

If plan 002 has not landed in your worktree, add the validator yourself
following the same shape, but do **not** duplicate it if it already exists.

**Verify**: `cd apps/backend && uv run python -c "from app import *"` → exit 0.

### Step 2: Add sign and verify helpers

In `apps/backend/app/routers/documents.py`, add two module-level helpers using
stdlib `hmac` and `hashlib` (both already available; `secrets` is already
imported in this file):

- `_sign_upload_key(key: str, user_id, expires_at_epoch: int) -> str` — returns
  a hex HMAC-SHA256 over a canonical joined string of the three inputs, keyed on
  `settings.UPLOAD_SIGNING_SECRET`.
- `_verify_upload_grant(key: str, user_id, expires: int, signature: str) -> bool`
  — recomputes and compares using **`hmac.compare_digest`** (constant-time —
  do not use `==`), and returns False if `expires` is in the past.

Use the same canonical string construction in both; a mismatch between them is
the most likely bug here, so build the string in one shared private function.

**Verify**: `cd apps/backend && uv run ruff check .` → exit 0.

### Step 3: Issue the grant at upload-init and enforce it at the proxy

In `init_document_upload`, after `presign_put` returns, compute
`expires = int(expires_at.timestamp())` and
`sig = _sign_upload_key(<the key that appears in upload_url>, current_user.id, expires)`.

**Important**: sign the key *as it appears in the returned `upload_url`*, which
for `S3Storage` is the **prefixed** key (`_prefixed_key` is applied inside
`presign_put`). Signing the unprefixed key while verifying the prefixed one is
the failure mode to avoid. Parse it back out of `upload_url`, or restructure so
both sides use one value.

Append `?expires=<expires>&sig=<sig>` to `upload_url` before returning it.

In `upload_document_bytes`, add `expires: int` and `sig: str` as query
parameters, and reject with **403** when `_verify_upload_grant(...)` fails,
before reading the body. Keep the existing `..` check and the size check.

**Behavior when `UPLOAD_SIGNING_SECRET` is empty** (local dev): skip
verification and log a warning once. This keeps `make start-backend` working
with no configuration, and the step-1 validator prevents that path from existing
in production. Do not silently skip without the warning.

**Verify**: `cd apps/backend && uv run pytest tests/test_documents_api.py -v` → all pass. If existing upload tests fail because they PUT without a signature, update them to go through `upload-init` first — that is the realistic flow and the correct fix. Do **not** disable verification to make them pass.

### Step 4: Update the stale comments

Update the comment at `apps/backend/app/routers/documents.py:148-149` — it
currently describes the unenforced contract as if it were enforced. Update the
comment block in `S3Storage.presign_put` (`storage.py:193-196`) that says
"Expiry is advisory here — the proxy is governed by bearer auth, not by a
signature," since that is exactly what this plan changes.

**Verify**: `grep -n 'advisory' apps/backend/app/services/storage.py` → no stale claim remains.

### Step 5: Regenerate the API client

The `upload-init` response is unchanged in shape (the signature rides inside the
existing `upload_url` string), but `upload_document_bytes` gained query
parameters, so the OpenAPI schema changes.

Run `make openapi`.

Then check whether any frontend code constructs the upload PUT URL manually
rather than using `upload_url` verbatim:
`grep -rn 'documents/upload' apps/ packages/ --include=*.ts --include=*.tsx`.
If it uses `upload_url` as returned, no frontend change is needed. If it rebuilds
the URL, it will drop the query string — that must be fixed to use `upload_url`
verbatim, and that file becomes in-scope.

**Verify**: `make openapi` → exit 0; `pnpm turbo run typecheck` → exit 0.

### Step 6: Add tests

In `apps/backend/tests/test_documents_api.py`:

- Happy path: `upload-init` → PUT to the returned `upload_url` (with its query
  string) → 204.
- **The regression test**: user A calls `upload-init`; user B (a different
  authenticated user) PUTs to A's key with A's signature → **403**. This is the
  vulnerability; assert it is closed.
- PUT with a tampered `sig` → 403.
- PUT with an `expires` in the past → 403.
- PUT with no `sig`/`expires` at all → 403.

Set `UPLOAD_SIGNING_SECRET` to a test value in these tests so verification is
active — otherwise the empty-secret bypass makes every assertion vacuous. This
is the single most important detail in the test setup.

**Verify**: `cd apps/backend && uv run pytest tests/test_documents_api.py -v` → all pass, 5 new tests.

## Test plan

Covered in step 6. Model after the existing upload tests in
`apps/backend/tests/test_documents_api.py`. The cross-user 403 is the test that
must fail against the pre-fix code — check that it does.

Verification: `cd apps/backend && uv run pytest -q` → all pass.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `pnpm turbo run typecheck` exits 0
- [ ] `make openapi` exits 0 and the regenerated files are included in the diff
- [ ] `grep -n 'compare_digest' apps/backend/app/routers/documents.py` returns a match (constant-time comparison used)
- [ ] A test exists in which a second user's PUT to another user's key returns 403, and it fails against pre-fix code
- [ ] `grep -rn 'storage.write' apps/backend/app/services/email_ingest.py apps/backend/app/routers/bank_imports.py` still shows those call sites unchanged
- [ ] `git diff --name-only` contains no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts in "Current state" do not match the live code.
- `grep -rn 'storage.write' apps/backend/app` reveals a caller reaching the
  write path over HTTP rather than in-process — the guard's placement then needs
  rethinking.
- The frontend constructs the upload URL manually in more than one place, or in
  a way where threading the query string is not a small edit.
- Existing upload tests cannot be made to pass without weakening verification.
- The prefixed-vs-unprefixed key question in step 3 turns out to be ambiguous
  for a backend other than `S3Storage` — report rather than guessing.

## Maintenance notes

- **`UPLOAD_SIGNING_SECRET` must be added to the deployment secrets** before
  this ships to production, or the step-1 validator will (correctly) refuse to
  start. Flag this to the operator explicitly — it is a deploy-coordination
  step, not a code step. It also belongs in `apps/backend/.env.example`
  (plan 011 covers that file).
- Rotating the secret invalidates in-flight upload grants — harmless, since the
  TTL is 15 minutes, but worth knowing during an incident.
- This closes the *write* side only. Read authorization on presigned GETs is
  unchanged: anyone holding a `file_url` can still fetch the object for the
  lifetime of the presigned URL. That is a separate decision the ADR should
  record.
- A reviewer should scrutinize: that signing and verification build the
  canonical string identically, that `compare_digest` is used rather than `==`,
  and that the empty-secret dev bypass cannot be reached in a production
  configuration.
