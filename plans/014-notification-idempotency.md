# Plan 014: Give notifications an idempotency key so retries are safe

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If a
> STOP condition occurs, stop and report — do not improvise.
>
> **Drift check (run first)**: `git diff --stat HEAD -- apps/backend/app/models/notification_log.py apps/backend/app/worker.py`

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plan 009 (already merged — JWKS + async send landed; this completes its step 4)
- **Category**: bug
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21

## Why this matters

`task_send_notification` wraps its whole body in a bare `except Exception`. Any
transient failure — a dropped DB connection, an error writing the notification
log — is logged and the job **reports success**. arq never retries, so the
notification is permanently lost with no queue-level signal. For a capital-call
notice that means **a limited partner is never told money is due, and nothing
alerts anyone.**

Plan 009 correctly refused to remove that catch, because removing it alone
creates a worse bug: the hazard window is `channel.send()` delivering a real
email, then the later `db.commit()` failing, then arq retrying the whole job and
sending a **second email to the same LP**. `NotificationLog` has no way to
detect that today — no `reference_type`/`reference_id` columns, no unique
constraint, no `job_id`.

This plan adds the missing idempotency key, then removes the catch. Order
matters: the key must exist before retries are enabled.

## Current state

`apps/backend/app/models/notification_log.py` — read it in full before starting.
It records a delivery attempt per channel but has no key that survives a retry.

`apps/backend/app/worker.py` — `task_send_notification`:
- early-return FK guards near the top (these are **correct** — a genuinely
  missing row is not retryable; keep them),
- a channel loop (`for channel_name in ("email",)` today),
- `NotificationRepository.create()` for the in-app row, which commits
  immediately in its own transaction,
- a later `db.commit()` for the log row,
- a blanket `except Exception` around all of it.

`reference_type` and `reference_id` are already **passed into the task as
arguments** but are never persisted anywhere queryable — that is precisely the
gap.

Migration conventions: `apps/backend/app/alembic/`. Generate with
`make migration` (prompts for a name), apply with `make upgrade`, revert with
`make downgrade`. Alembic files are excluded from all linters.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `cd apps/backend && uv run pytest -q` | `456 passed` (plus your new tests), 0 failed |
| Lint | `make lint` (from repo root) | exit 0 |
| New migration | `make migration` | creates a revision in `app/alembic/versions/` |
| Apply / revert | `make upgrade` / `make downgrade` | exit 0 both ways |

Environment for test runs (both needed):
```
export APP_DOMAIN=localhost
export APP_DATABASE_DSN="$(grep '^APP_DATABASE_DSN=' /Users/andy/Developer/edenscale/apps/backend/.env | cut -d= -f2- | sed 's|/\([^/]*\)$|/taven_wt014|')"
```
Never print the DSN — it contains a password.

## Scope

**In scope**:
- `apps/backend/app/models/notification_log.py`
- `apps/backend/app/alembic/versions/<new>.py` (generated)
- `apps/backend/app/repositories/notification_repository.py`
- `apps/backend/app/worker.py` (`task_send_notification` only)
- `apps/backend/tests/test_worker_tasks.py`
- `apps/backend/app/models/__init__.py` / `app/repositories/__init__.py` if exports change

**Out of scope**:
- `app/services/notifications.py` fan-out logic — do not change how events are
  raised.
- `task_draft_letter` — separate plan.
- The channel implementations in `app/services/channels/`.
- Any other task in `worker.py`.

## Steps

### Step 1: Add the idempotency key to `NotificationLog`

Add persisted columns so a retry can recognise work already done. At minimum:
`reference_type`, `reference_id`, and a delivery-status marker if one is not
already present.

Add a **unique constraint** over the tuple that identifies one delivery:
`(notification_type, reference_type, reference_id, channel, recipient)`.
Adjust the exact column names to match what the model and task actually use —
read both first; do not guess.

**Nullable reference values are the hard case.** Some notification types have no
`reference_type`/`reference_id`. A unique constraint treats `NULL`s as distinct
in PostgreSQL, so rows with nulls will not dedupe. Handle this deliberately —
either substitute a sentinel string (e.g. `''`) instead of `NULL`, or use a
partial unique index that only applies when the reference columns are non-null
and accept that unreferenced notifications remain un-deduped. **State which you
chose and why in your report.**

**Verify**: `cd apps/backend && uv run python -c "from app import *"` → exit 0.

### Step 2: Generate and exercise the migration

Run `make migration`, name it something like `notification_log_idempotency`.
Inspect the generated file — autogenerate sometimes misses constraints or emits
spurious drops. Fix it by hand if needed.

Then exercise it **both ways**: `make upgrade`, then `make downgrade`, then
`make upgrade` again. A migration that cannot be reverted is a liability.

**Verify**: all three commands exit 0, and the constraint exists after upgrade.

### Step 3: Record deliveries and skip already-delivered channels

In `NotificationRepository` (or wherever log rows are written), add a method
that records a successful channel delivery, and one that answers "has this
(type, reference, channel, recipient) already been delivered?"

Use the repository pattern — per `CLAUDE.md`, business logic belongs in
repositories, not in the task.

In `task_send_notification`, **before** calling `channel.send(...)` for a given
channel, check whether that channel was already delivered for this key; if so,
skip it. **After** a successful send, record it.

The recording write must be durable before the next channel is attempted —
otherwise a crash between send and record reopens the same hole.

**Verify**: `cd apps/backend && uv run pytest tests/test_worker_tasks.py -v` → all pass.

### Step 4: Remove the blanket catch

Now — and only now — remove the outer `except Exception` from
`task_send_notification` so unexpected failures propagate and arq retries.

**Keep the early-return FK guards.** They handle genuinely-missing rows, which
are not retryable.

Set `max_tries` explicitly in `WorkerSettings` (or at enqueue time) rather than
relying on the arq default, so the retry budget is a decision rather than an
accident. State the value you chose.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 5: Tests

In `apps/backend/tests/test_worker_tasks.py`:

- **The regression test**: a transient failure inside the task now
  **propagates** (the task raises) instead of returning success. This must fail
  against the pre-fix code — verify and report before/after.
- A retry after a partial send does **not** re-send an already-delivered
  channel. This is the test that proves the idempotency key works; without it
  the whole plan is unverified.
- The existing FK-guard behavior still returns early without raising.
- Two different notifications with the same reference but different channels are
  both delivered (the constraint must not over-dedupe).

**Verify**: `cd apps/backend && uv run pytest -q` → all pass, 4+ new tests.

## Done criteria

- [ ] `cd apps/backend && uv run pytest -q` → 0 failures
- [ ] `make lint` (repo root) → exit 0
- [ ] `make upgrade` and `make downgrade` both exit 0
- [ ] `task_send_notification` has no blanket `except Exception` around its body
- [ ] A test proves a retry does not re-send an already-delivered channel
- [ ] A test proves a transient failure propagates (fails pre-fix)
- [ ] `max_tries` is set explicitly
- [ ] `git diff --name-only` contains no file outside the in-scope list

## STOP conditions

- The unique constraint cannot be added because existing rows violate it —
  report the duplicate shape; a data cleanup decision is needed first.
- You cannot make the "already delivered?" check durable before the next
  channel send without restructuring `app/services/notifications.py` (out of
  scope).
- Removing the catch breaks existing worker tests in a way revealing they
  depended on failures being swallowed — report which.
- The nullable-reference problem in step 1 has no clean answer for the
  notification types actually in use — report what you found rather than
  shipping a constraint that silently fails to dedupe.

## Maintenance notes

- The channel loop is single-entry today (`("email",)`). The dedupe design must
  not assume that — a second channel is the scenario it exists for.
- Once this lands, notification loss becomes visible as arq retries and
  eventually dead-letters, rather than silent success. Expect to see failures
  that were always happening but were invisible.
- Reviewer should scrutinize: that the delivery record is committed **before**
  the next channel send, and that the FK early-returns survived.
