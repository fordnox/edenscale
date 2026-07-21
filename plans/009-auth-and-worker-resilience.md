# Plan 009: Survive Hanko key rotation and stop losing notifications silently

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/core/auth.py apps/backend/app/worker.py apps/backend/app/services/channels/email_channel.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: bug
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

Three independent resilience defects, grouped because each is small and they
share a theme: failures that are invisible until they are outages.

**(a) Hanko key rotation causes a rolling authentication outage.** The JWKS
cache has a one-hour TTL and no invalidation path. When a token arrives signed
with a `kid` not in the cached set, the code raises 401 immediately instead of
refetching. So when Hanko rotates its signing key, every request signed with the
new key fails for up to an hour — independently per API process, with no
operator lever short of a restart. The fix is already sitting in the file
unused: a `PyJWKClient` is constructed with its own caching and then never
referenced, shadowed by a hand-rolled cache.

**(b) Notifications are lost silently.** `task_send_notification` wraps its
entire body in a bare `except Exception`, including the commit. Any transient
failure — a dropped DB connection, an error inserting the notification log — is
logged and the job reports **success**. arq never retries, so the notification
is permanently gone with no queue-level signal. For a capital-call notice, that
means an LP is never told money is due. The narrow FK guards earlier in the same
function show the author already knew which failures are legitimately
non-retryable; the outer catch swallows everything else too.

**(c) The email channel blocks the worker's event loop.** It calls Resend's
**synchronous** send inside an `async def`, so every notification email
serializes the whole worker: arq's concurrency setting buys nothing, and a slow
Resend response stalls unrelated jobs. The codebase is already inconsistent
about this — the drip path correctly uses the async API.

## Current state

`apps/backend/app/core/auth.py:20-24` — the unused client:

```python
jwks_client = PyJWKClient(
    f"{settings.HANKO_API_URL}/.well-known/jwks.json",
    cache_keys=True,
    lifespan=3600,
)
```

`apps/backend/app/core/auth.py:29-41` — fails without refetching:

```python
def _get_signing_key(jwks: dict[str, Any], token: str) -> jwt.algorithms.RSAAlgorithm:
    """Extract the correct signing key from JWKS based on the token's kid header."""
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find matching signing key",
    )
```

`apps/backend/app/core/auth.py:44-59` — the hand-rolled cache with no invalidation:

```python
async def get_hanko_jwks() -> dict[str, Any]:
    """Fetch Hanko JWKS from the well-known endpoint, with 1-hour cache."""
    global _jwks_cache

    now = time.time()
    if _jwks_cache and (now - _jwks_cache.get("fetched_at", 0)) < _JWKS_CACHE_TTL:
        return _jwks_cache
    ...
```

`apps/backend/app/worker.py:142-147` — the blanket catch (line numbers
approximate; read the function):

```python
    except Exception:
        logger.exception(...)
```

wrapping a body that includes `db.commit()` (~line 135) and the deliberate
early-return FK guards (~lines 45-71).

`apps/backend/app/services/channels/email_channel.py:152`:

```python
        response = resend.Emails.send(params)
```

The async precedent to follow, `apps/backend/app/services/drip.py:72`:

```python
        await resend.Events.send_async(...)
```

Relevant tests: `apps/backend/tests/test_worker_tasks.py`,
`apps/backend/tests/test_notifications_api.py`, `apps/backend/tests/test_drip.py`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Targeted | `cd apps/backend && uv run pytest tests/test_worker_tasks.py tests/test_drip.py tests/test_notifications_api.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Import smoke test | `cd apps/backend && uv run python -c "from app import *"` | exit 0 |

## Scope

**In scope**:
- `apps/backend/app/core/auth.py`
- `apps/backend/app/worker.py` (`task_send_notification` only)
- `apps/backend/app/services/channels/email_channel.py`
- `apps/backend/tests/test_worker_tasks.py`, and a new auth test file

**Out of scope** (do NOT touch):
- Token **validation** semantics — algorithm, audience, issuer checks stay
  exactly as they are. This plan changes only key *retrieval*.
- `task_draft_letter` — it has a related retry-idempotency gap, but changing
  retry behavior there without a dedupe guard would create duplicate LLM drafts.
  Separate plan.
- `app/tasks.py`'s per-call Redis pool — real inefficiency, separate change.
- `app/services/drip.py` — already correct; use it as the reference only.
- The notification **fan-out** logic in `app/services/notifications.py`.

## Git workflow

- Branch: `advisor/009-auth-worker-resilience`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Refresh the JWKS cache on an unknown `kid`

In `apps/backend/app/core/auth.py`, make an unknown `kid` trigger **one** forced
cache refresh and retry before raising 401.

Two acceptable approaches — pick one and say which in your report:

**(i) Preferred — use the existing `PyJWKClient`.** Replace the hand-rolled
cache and `_get_signing_key` with `jwks_client.get_signing_key_from_jwt(token)`.
PyJWKClient already handles caching and refresh-on-miss. This deletes code
rather than adding it. Confirm the library version in `pyproject.toml` supports
it, and check whether `get_signing_key_from_jwt` is sync (it is, in PyJWT) —
which matters because the surrounding function is `async`; wrap it in
`run_in_threadpool` if it performs network I/O.

**(ii) Fallback — add invalidation to the existing cache.** Give
`get_hanko_jwks` a `force: bool = False` parameter that bypasses the TTL, and on
a `kid` miss call it once with `force=True` and retry the lookup.

**Either way**: the refresh must be attempted **at most once** per request. An
unbounded refresh path lets anyone force repeated outbound JWKS fetches by
sending tokens with random `kid` values. Guard it explicitly.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 2: Test the rotation path

Add a test (new file `apps/backend/tests/test_auth_jwks.py`, or extend an
existing auth test if one exists — check `tests/test_hanko_service.py` first).

Cover:
- A token whose `kid` is absent from the cached JWKS triggers exactly **one**
  refetch and then validates successfully once the new key is present.
- A token whose `kid` is absent from *both* the cached and the refetched JWKS
  raises 401 and does **not** refetch more than once.

Stub the JWKS fetch (monkeypatch, or `httpx.MockTransport` as
`tests/test_hanko_service.py` may already do) — do not make real network calls.
Assert on the **number of fetches**; that is the whole point of the test.

**Verify**: `cd apps/backend && uv run pytest tests/test_auth_jwks.py -v` → all pass.

### Step 3: Switch the email channel to the async send

In `apps/backend/app/services/channels/email_channel.py:152`, change
`resend.Emails.send(params)` to `await resend.Emails.send_async(params)`.

Keep the surrounding `try/except` and the returned result dict unchanged.
Verify the async call returns the same shape — the code reads `response["id"]`;
confirm `send_async` provides it, and if the shape differs, adapt the read
rather than the contract.

**Verify**: `cd apps/backend && uv run pytest tests/test_notifications_api.py tests/test_drip.py -v` → all pass.

### Step 4: Narrow the blanket exception handler

In `task_send_notification` in `apps/backend/app/worker.py`:

- **Keep** the early-return FK guards. Those are correct: a genuinely missing
  row is not retryable.
- **Remove** the blanket `except Exception` around the whole body so that
  unexpected failures propagate and arq retries them.

The hazard this creates: a retry could resend emails that already went out
within the same job. Before removing the catch, check how the job iterates
channels. If a single job sends across multiple channels, record per-channel
delivery state (there is a `NotificationLog` model — check whether it already
gives you this) so a retry skips channels already delivered.

**If you cannot establish that retries are safe from the code you can read,
STOP and report.** A retry storm that re-emails every LP is worse than the
silent-loss bug this fixes. Do not guess.

**Verify**: `cd apps/backend && uv run pytest tests/test_worker_tasks.py -v` → all pass.

### Step 5: Test the failure path

Add to `apps/backend/tests/test_worker_tasks.py`:

- A transient failure inside the task **propagates** (the task raises) rather
  than returning success — this is the regression test for the silent-loss bug.
- A genuinely missing FK row still returns early without raising (the existing
  guards still work).
- If you added per-channel delivery state: a retry after a partial send does not
  re-send the already-delivered channel.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

## Test plan

Steps 2 and 5. The load-bearing assertions: the JWKS refetch **count**, and that
a transient failure now propagates instead of being swallowed.

Model after `apps/backend/tests/test_worker_tasks.py` and
`tests/test_hanko_service.py`.

Verification: `cd apps/backend && uv run pytest -q` → all pass.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `cd apps/backend && uv run python -c "from app import *"` exits 0
- [ ] An unknown `kid` triggers at most one JWKS refetch — pinned by a test asserting the count
- [ ] `grep -n 'resend.Emails.send(' apps/backend/app/services/channels/email_channel.py` returns **no** match (only the async form remains)
- [ ] `task_send_notification` has no blanket `except Exception` around its whole body
- [ ] A test asserts a transient failure propagates out of `task_send_notification`
- [ ] Token validation parameters (algorithm, audience) are unchanged — `git diff` confirms
- [ ] `git diff --name-only` contains no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- You cannot establish from the code that retrying `task_send_notification` is
  safe against duplicate sends. Report what you found; leave the catch in place.
- `resend.Emails.send_async` does not exist in the pinned `resend` version, or
  returns a different result shape you cannot map cleanly.
- Removing the blanket catch makes existing worker tests fail in a way that
  reveals they depended on failures being swallowed — report which.
- Approach (i) in step 1 changes token validation behavior in any way beyond key
  retrieval (e.g. different audience handling) — fall back to approach (ii).
- Any change would require touching `app/services/notifications.py`.

## Maintenance notes

- After step 1, the module should have **one** JWKS caching mechanism, not two.
  If you take approach (ii), delete the unused `PyJWKClient` at lines 20-24 so
  the next reader is not misled — a second, unused cache is exactly what made
  this bug hard to see.
- arq's `max_tries` default now matters for notifications. Check it in
  `WorkerSettings` and set it explicitly rather than relying on the default, so
  the retry budget is a decision rather than an accident.
- Deliberately deferred and worth scheduling: `task_draft_letter` has the same
  retry shape but no dedupe, so a failure after persistence yields duplicate
  drafts and duplicate OpenRouter spend; and `enqueue_task` opens and closes a
  fresh Redis pool per call, so a 100-LP capital-call fan-out performs 100
  connect/disconnect cycles on the request path.
- A reviewer should scrutinize: the JWKS refresh is bounded (cannot be forced
  repeatedly by an attacker), and the retry-safety argument in step 4 is
  explicit rather than assumed.
