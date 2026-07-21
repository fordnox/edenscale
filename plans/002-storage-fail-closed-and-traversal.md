# Plan 002: Close the dev-storage path traversal and make storage config fail closed

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/services/storage.py apps/backend/app/routers/documents.py apps/backend/app/core/config.py .kamal/secrets`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: security
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

Three separate defects chain into one serious exposure.

1. `settings.STORAGE_BACKEND` defaults to `"local"`. A deployment that fails to
   set that environment variable silently runs `LocalDevStorage` in production
   — it **fails open**, to the backend that is explicitly documented as
   unsuitable for production.
2. In that state, `GET /dev-storage/{key}` is mounted with **no authentication
   token check** (unlike its sibling POST route, which does check one) and
   **no** `..` filter.
3. `LocalDevStorage.read` builds its path as bare `self.base_dir / key`.
   `pathlib` does not normalize, so `..` segments resolve against the real
   filesystem.

Chained, one missing environment variable turns into an unauthenticated
arbitrary-file-read of the API container's filesystem — which includes the
backend's `.env`, holding the Resend key, the OpenRouter key, S3 credentials,
and the email-ingest shared secret.

ADR-002 (`docs/decisions/adr-002-storage-port-pattern.md:77`) accepts that
dev-storage serves *uploaded blobs* without authentication. It does **not**
contemplate reads outside the storage directory. This is implementation risk
beyond the recorded decision, so it is in scope to fix rather than settled by
the ADR.

## Current state

`apps/backend/app/core/config.py:48-49` — the fail-open defaults:

```python
    STORAGE_BACKEND: str = "local"
    DEV_STORAGE_TOKEN: str = "dev-storage"
```

`DEV_STORAGE_TOKEN` has a hardcoded default committed to this repository, and
it is **absent** from the `env: secret:` list in `config/deploy.yml`, so a
production deploy runs on that published default.

`apps/backend/app/services/storage.py:104-113` — no containment check:

```python
    def write(self, key: str, content: bytes, mime_type: str | None = None) -> None:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes | None:
        path = self.base_dir / key
        if not path.exists() or not path.is_file():
            return None
        return path.read_bytes()
```

`delete` (immediately below) has the same shape.

`apps/backend/app/routers/documents.py:364-372` — the unauthenticated read
route, with no `..` filter:

```python
@dev_storage_router.get("/dev-storage/{key:path}")
async def dev_storage_download(key: str):
    storage = _dev_storage_only()
    blob = storage.read(key)
    if blob is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
        )
    return Response(content=blob, media_type="application/octet-stream")
```

Contrast the POST sibling at `apps/backend/app/routers/documents.py:349-358`,
which **does** gate on a token — this asymmetry is the bug:

```python
async def dev_storage_upload(key: str, request: Request):
    storage = _dev_storage_only()
    expected = settings.DEV_STORAGE_TOKEN
    provided = request.headers.get("x-dev-storage-token")
    if not expected or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid dev storage token",
        )
```

The existing `..` rejection idiom to copy is at
`apps/backend/app/routers/documents.py:159-162`:

```python
    if ".." in key.split("/") or key.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage key"
        )
```

`.kamal/secrets:13` sets `DEBUG=1` as a literal value — every other entry in
that file is a shell indirection. `apps/backend/app/core/config.py:9` defaults
`DEBUG` to `False`, so production explicitly turns it on.

Existing storage tests to model new ones on: `apps/backend/tests/test_storage_s3.py`.
Note `app.services.storage.reset_storage()` exists for swapping the singleton
between test cases (documented in ADR-002).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Storage tests | `cd apps/backend && uv run pytest tests/test_storage_s3.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Import smoke test | `cd apps/backend && uv run python -c "from app import *"` | exit 0 |

## Scope

**In scope**:
- `apps/backend/app/services/storage.py`
- `apps/backend/app/routers/documents.py` (dev-storage routes only)
- `apps/backend/app/core/config.py`
- `.kamal/secrets` (the `DEBUG` line only)
- `apps/backend/tests/test_storage_local.py` (create)

**Out of scope** (do NOT touch):
- `PUT /documents/upload/{key:path}` at `apps/backend/app/routers/documents.py:144`
  — that route's missing caller-to-key binding is a **separate, larger** fix
  owned by plan 003. Do not attempt it here; the two changes would conflict.
- `S3Storage` — its behavior is correct and covered by `test_storage_s3.py`.
- Any `.env` file — never read, write, or print one.
- `config/deploy.yml` — adding `DEV_STORAGE_TOKEN` to its secret list is
  deliberately *not* the fix; step 3 removes the need for the token in
  production entirely.

## Git workflow

- Branch: `advisor/002-storage-fail-closed`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add path containment to `LocalDevStorage`

In `apps/backend/app/services/storage.py`, add a private helper on
`LocalDevStorage`:

```python
    def _resolve(self, key: str) -> Path:
        """Resolve ``key`` inside ``base_dir``, refusing any escape.

        ``pathlib`` does not normalize ``..``; without this check a key like
        ``../../etc/passwd`` reads outside the storage root.
        """
        root = self.base_dir.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Storage key escapes the storage root: {key!r}")
        return path
```

`Path.is_relative_to` requires Python 3.9+; this project targets 3.12, so it is
available.

Use `self._resolve(key)` in **all three** of `write`, `read`, and `delete` in
place of `self.base_dir / key`. Keep every other line of those methods as-is.

**Verify**: `cd apps/backend && uv run python -c "from app import *"` → exit 0.

### Step 2: Reject traversal keys at the dev-storage routes

In `apps/backend/app/routers/documents.py`, apply the same `..` rejection used
at line 159 to **both** `dev_storage_upload` and `dev_storage_download`. Extract
it into a small module-level helper (e.g. `_reject_unsafe_key(key: str) -> None`)
and call it from all three sites — the two dev-storage routes and the existing
check at line 159 — so there is one implementation rather than three copies.

**CORRECTED after execution — do NOT add a token check to `dev_storage_download`.**

This plan originally instructed adding the same header token gate that
`dev_storage_upload` uses. That is **unimplementable and was my error**. Verified
during execution:

- `download_url` is consumed as a plain link navigation — e.g.
  `apps/investor/src/pages/ReportsPage.tsx:111` is `<a href={latest.download_url} download>`,
  and the same shape appears in `apps/manager/src/components/documents/DocumentDetail.tsx:66`
  and `apps/manager/src/pages/DocumentsPage.tsx:317`. A browser link click
  cannot attach a custom header, so a header gate would break every real
  local-dev document download, not merely a test.
- `LocalDevStorage.presign_get` (`app/services/storage.py:99-101`) returns
  `self._url_for(key)` — a bare URL carrying no credential.

It was also **overreach beyond the recorded decision**. ADR-002 explicitly
accepts that `LocalDevStorage` serves *uploaded blobs* without authentication on
a dev box. What ADR-002 does not sanction — and what this plan legitimately
fixes — is (a) reading *outside* the storage root, closed by step 1's
containment, and (b) a configuration that fails open into this backend in
production, closed by step 3's validator. With both closed, the residual
unauthenticated-blob-read is the documented, accepted dev-only tradeoff.

If authenticated dev reads are ever wanted, the correct design is a
query-string token embedded by `presign_get` (mirroring how `S3Storage.presign_get`
embeds its signature in the URL), validated by the route — not a header. That is
a design change, out of scope here, and recorded in plans/README.md as deferred.

**Verify**: `cd apps/backend && uv run pytest tests/test_documents_api.py -v` → all pass.

### Step 3: Make storage configuration fail closed

In `apps/backend/app/core/config.py`:

- Change `DEV_STORAGE_TOKEN` to default to `""` (empty). The existing
  `if not expected` branch in `dev_storage_upload` already treats an empty
  token as "reject", so an unset token now denies rather than admits. This
  removes the published default as a credential entirely.
- Add a validation that refuses to start in a production-shaped configuration
  with the local backend. Implement as a `@model_validator(mode="after")` on
  `Settings` (this project uses pydantic-settings v2 — match the existing style
  in the file): if `STORAGE_BACKEND == "local"` **and** `DEBUG` is false **and**
  `APP_DOMAIN` is not a localhost value, raise `ValueError` with a message
  naming `STORAGE_BACKEND`.

Do **not** simply remove the `"local"` default — local development depends on
it, and ADR-002 lists trivial onboarding as a core benefit. The validator
preserves that while closing the production path.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures. If the validator
breaks the test suite's settings, the test environment is localhost-shaped and
should pass; if it does not, STOP rather than weakening the validator.

### Step 4: Turn off `DEBUG` in the deployed environment

In `.kamal/secrets`, change line 13 from the truthy literal to `DEBUG=0`.

Change **only** that line. Do not read, echo, modify, or reproduce any other
line in that file — the rest are shell indirections that resolve to live
credentials.

**Verify**: `grep -n '^DEBUG' .kamal/secrets` → shows `DEBUG=0`, and
`git diff --stat .kamal/secrets` → 1 file changed, 1 insertion, 1 deletion.

### Step 5: Add tests

Create `apps/backend/tests/test_storage_local.py`, modeled structurally on
`apps/backend/tests/test_storage_s3.py`. Cover:

- `LocalDevStorage.write`/`read`/`delete` round-trip for a normal key (happy path)
- `read` with a traversal key raises `ValueError` (**this is the regression test
  for the vulnerability** — assert it raises, not that it returns `None`)
- `write` with a traversal key raises `ValueError`
- `delete` with a traversal key raises `ValueError`
- `GET /dev-storage/{key}` without the token header returns 401
- `GET /dev-storage/` with a traversal key returns 400 and does **not** return
  file bytes

Use a `tmp_path` fixture for `base_dir` so no test writes into the real
`dev_storage` directory. Call `reset_storage()` if you swap the singleton.

**Verify**: `cd apps/backend && uv run pytest tests/test_storage_local.py -v` → all pass.

## Test plan

Covered in step 5. The load-bearing assertion is that a traversal key **raises**
rather than silently returning `None` — a `None` return would look like a pass
while leaving the underlying `path.exists()` check reachable.

Model after `apps/backend/tests/test_storage_s3.py`.

Verification: `cd apps/backend && uv run pytest -q` → all pass, including ~7 new tests.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `cd apps/backend && uv run python -c "from app import *"` exits 0
- [ ] `grep -n 'self.base_dir / key' apps/backend/app/services/storage.py` returns **no matches**
- [ ] `grep -n 'DEV_STORAGE_TOKEN' apps/backend/app/core/config.py` shows an empty-string default
- [ ] `grep -n '^DEBUG' .kamal/secrets` shows `DEBUG=0`
- [ ] `apps/backend/tests/test_storage_local.py` exists and contains a test asserting a traversal key raises
- [ ] `git diff --name-only` contains no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts in "Current state" do not match the live code.
- Adding the token check to `dev_storage_download` breaks existing tests — that
  would mean some test or frontend path reads dev-storage anonymously, and the
  fix needs to thread the token through instead. Report what broke.
- The `model_validator` in step 3 causes the test suite to fail to construct
  `Settings`. Report the error; do not weaken or delete the validator to get green.
- You find yourself needing to modify `PUT /documents/upload/{key:path}` — that
  is plan 003's scope.
- Any step would require reading or printing the contents of a `.env` file or
  any line of `.kamal/secrets` other than the `DEBUG` line.

## Maintenance notes

- **CI must set `APP_DOMAIN=localhost`** (or `DEBUG=1`) for the backend job, or
  step 3's validator refuses to construct `Settings` and the whole suite errors
  out. A developer checkout is unaffected because `apps/backend/.env` already
  sets `APP_DOMAIN=localhost` — the failure only appears where no `.env` exists,
  which is exactly the CI case and the worktree case. Coordinate this with plan
  001's `ci.yml`. Better still, have `tests/conftest.py` force
  `os.environ["APP_DOMAIN"] = "localhost"` alongside the `SUPERADMIN_EMAIL` and
  `RESEND_API_KEY` overrides it already sets, so the suite is self-contained.
- Setting `DEV_STORAGE_TOKEN` to default `""` broke two pre-existing tests in
  `tests/test_documents_api.py` (the PUT gate rejects when no token is
  configured). Resolved by monkeypatching the token in that file's existing
  `reset_local_storage` autouse fixture — worth knowing if similar tests appear.
- **Rotation is required and is not done by this plan.** `DEV_STORAGE_TOKEN`'s
  old default is published in this repository's git history and must be treated
  as burned. Flag to the operator that it should be rotated, along with
  `EMAIL_INGEST_TOKEN` if plan 005 lands.
- The `is_relative_to` containment check is the single defense for local
  storage. Any future `StoragePort` implementation that touches a filesystem
  needs the same check — it belongs in the implementation, not the routes,
  which is why step 1 puts it there.
- ADR-002 needs updating to record that dev-storage's accepted unauthenticated
  exposure covers uploaded blobs only, never reads outside the storage root.
  That edit is plan 010's job, not this one's.
- Reviewer should scrutinize: that the validator in step 3 cannot be satisfied
  by a production deploy that omits `STORAGE_BACKEND`, and that step 4 changed
  exactly one line of `.kamal/secrets`.
