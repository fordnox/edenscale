# Plan 020: Make email ingest and letter drafting idempotent, and add request correlation

> **Executor instructions**: Follow step by step. Run every verification command.
> If a STOP condition occurs, stop and report — do not improvise.
>
> **Drift check**: `git diff --stat HEAD -- apps/backend/app/services/email_ingest.py apps/backend/app/worker.py apps/backend/app/middleware`

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (one migration; changes an external contract additively)
- **Depends on**: plan 014 (merged first — it establishes the idempotency pattern to follow)
- **Category**: bug | dx
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21

## Why this matters

**(a) Email ingest is not idempotent.** `POST /email-ingest/documents` takes no
message id, and `email_ingest.py` generates a fresh random storage key per call,
so nothing collides to signal a repeat. Worse, `storage.write` then
`documents.create` (which commits) run **per attachment inside a loop** — an
exception on attachment 3 leaves attachments 1–2 committed and returns a 500,
which the Cloudflare Worker will retry. Any retry — network blip, mid-loop
failure, at-least-once delivery — re-ingests the whole email: duplicate
`Document` rows, duplicate blobs, duplicate `notify_document_uploaded` emails to
every manager, and duplicate `enqueue_draft_letter` jobs burning OpenRouter
tokens.

**(b) `task_draft_letter` duplicates drafts on retry.** Unlike
`task_send_notification` it has no blanket catch, so an exception *after*
`create_draft` commits propagates and arq re-runs the whole task — producing N
identical announcement drafts for one document, each costing a full LLM call.

**(c) There is no request correlation.** Ten modules call
`logging.getLogger(__name__)`, there is no `logging.basicConfig`, no structured
logging, and no request id anywhere. Notifications cross a process boundary
(request → `event_bus` → arq worker → channel), so when an LP reports a missing
capital-call email there is **no id tying the worker's log line back to the
originating request**. Debugging that today means adding log statements and
redeploying.

Credit where due: there is no `print()` debugging anywhere in this codebase. The
discipline is good; the correlation is the gap.

## Current state

`apps/backend/app/services/email_ingest.py`:
- ~line 122: `logical_key = f"documents/{secrets.token_urlsafe(16)}/{safe_name}"`
  — fresh randomness per call, so nothing ever collides.
- ~lines 126-144: `storage.write` then `self.documents.create` (commits) inside
  the per-attachment loop.
- ~line 149: auto-enqueues a draft.

`apps/backend/app/schemas/email_ingest.py` — `EmailIngestRequest` carries
sender, recipient, subject, attachments. No message id.

`apps/backend/app/routers/email_ingest.py` — token-gated via
`require_ingest_token`; 404 when the feature is off, 403 on mismatch.

`apps/backend/app/worker.py` — `task_draft_letter` (~lines 169-246): only
`finally: db.close()`; `create_draft` commits at ~225-239, then
`await notify_letter_drafted(...)`. Only `draft_letter` itself is wrapped in a
log-and-drop `try/except` (~212-223); the persistence step is not.

`apps/backend/app/middleware/` contains only `audit_context.py` — read it, it
establishes the **contextvar pattern** this plan should follow for the request
id.

`apps/backend/app/tasks.py` — `enqueue_task` builds the job kwargs.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `cd apps/backend && uv run pytest -q` | all pass, 0 failed |
| Lint | `make lint` (repo root) | exit 0 |
| Migration | `make migration`, `make upgrade`, `make downgrade` | exit 0 |
| Ingest tests | `cd apps/backend && uv run pytest tests/test_email_ingest.py -v` | all pass |

Environment (both): `export APP_DOMAIN=localhost` and an isolated
`APP_DATABASE_DSN` (suffix `_wt020`). Never print the DSN.

## Scope

**In scope**:
- `apps/backend/app/services/email_ingest.py`, `app/schemas/email_ingest.py`, `app/routers/email_ingest.py`
- `apps/backend/app/worker.py` (`task_draft_letter` only)
- `apps/backend/app/middleware/` (new request-id middleware), `app/main.py` (register it)
- `apps/backend/app/tasks.py` / `app/core/event_bus.py` (propagate the id into job kwargs)
- a generated migration + the affected model
- `apps/backend/tests/test_email_ingest.py`, `test_worker_tasks.py`, `test_documents_draft_letter.py`

**Out of scope**:
- **Sender authenticity / DKIM verification.** The backend trusts a self-asserted
  `sender_email` for org routing. That is a real finding, but closing it requires
  coordinating with the Cloudflare Worker in `apps/email-ingest`, which is not
  audited and not in scope here. Do **not** add a required `dkim_verified` field
  — it would drop every ingest until the Worker is updated.
- `task_send_notification` — plan 014 owns it.
- Replacing the logging library wholesale.

## Steps

### Step 1: Accept and persist an ingest message id

Add an optional `message_id` to `EmailIngestRequest`. Persist it — either on
`Document` or in a small ingest-log table — with a **unique index**, scoped so
that a repeat of the same message is detectable.

Optional, not required: the Worker may not send it yet. When absent, fall back to
current behavior (no dedupe) rather than rejecting. Note in your report that
dedupe only engages once the Worker supplies the field.

Generate the migration with `make migration`, inspect it, and exercise it **both
ways**.

**Verify**: `make upgrade` and `make downgrade` both exit 0.

### Step 2: Make `ingest()` all-or-nothing, and return the prior result on repeat

Two changes:

- **Atomicity**: restructure the per-attachment loop so a failure partway
  through does not leave earlier attachments committed. Follow the
  validate-then-write shape already used in
  `bank_import_repository.apply()` (plan 003) — resolve and validate every
  attachment first, then write, then a single commit. Note `storage.write` is
  not transactional; a blob written for an attachment whose row is rolled back
  becomes an orphan. Either write blobs only after validation passes, or accept
  and document orphaned blobs. State which.
- **Idempotency**: when `message_id` is present and already seen, return the
  prior result without re-creating documents, re-notifying, or re-enqueuing
  drafts.

**Verify**: `cd apps/backend && uv run pytest tests/test_email_ingest.py -v` → all pass.

### Step 3: Stop `task_draft_letter` duplicating drafts

Before creating a draft, check for an existing one keyed on
`(document_id, sender_user_id)` — or whatever key actually identifies "the draft
for this document" — and return early if present.

Wrap the create-and-notify pair so a failure in `notify_letter_drafted` cannot
trigger a re-run that re-drafts. Note `notify_letter_drafted` is itself
`try/except`-wrapped in `notifications.py`, so the exposure is narrower than the
general case — verify that before deciding how much machinery is warranted, and
say what you found.

Check `WorkerSettings` for `max_tries`; set it explicitly if unset.

**Verify**: `cd apps/backend && uv run pytest tests/test_documents_draft_letter.py tests/test_worker_tasks.py -v` → all pass.

### Step 4: Add request correlation

Create `apps/backend/app/middleware/request_id.py`: read an inbound
`X-Request-ID` or generate one, stash it in a `ContextVar`, and echo it on the
response. **Follow the existing pattern in `audit_context.py`** — it already
does exactly this shape for the actor user id.

Register it in `app/main.py` alongside `AuditContextMiddleware`. Mind ordering:
Starlette's `add_middleware` inserts at index 0, so the last-added middleware is
outermost. The request id must be set before anything that logs.

Add a logging formatter that emits the id, and configure logging once at startup
(there is no `logging.basicConfig` today).

Then propagate: have `event_bus` / `enqueue_task` copy the current request id
into the arq job kwargs, and have the worker restore it into its own contextvar
so worker log lines carry the originating request's id. **This is the part that
actually pays off** — it's what links a missing LP email back to the request that
should have sent it.

The job-payload change needs care so in-flight jobs enqueued before deploy don't
break on a missing kwarg — make it optional with a default.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 5: Tests

- Re-posting the same `message_id` creates no second `Document`, fires no second
  notification, enqueues no second draft job. **Must fail pre-fix** — verify and
  report before/after.
- A failure on attachment 3 leaves **no** attachments committed.
- A repeat `task_draft_letter` for the same document creates no second draft.
- A request id present on the inbound request appears on the response and in the
  contextvar; an absent one is generated.
- An enqueued job carries the request id, and an old-style job without one still
  runs.

**Verify**: `cd apps/backend && uv run pytest -q` → all pass, 6+ new tests.

## Done criteria

- [ ] `cd apps/backend && uv run pytest -q` → 0 failures
- [ ] `make lint` → exit 0
- [ ] Migration exercised up **and** down
- [ ] A test proves repeat ingest is a no-op (fails pre-fix)
- [ ] A test proves partial ingest failure commits nothing
- [ ] A test proves repeat draft-letter creates no duplicate
- [ ] Request id round-trips and reaches worker job kwargs
- [ ] `EmailIngestRequest.message_id` is **optional** (no ingest is rejected for lacking it)
- [ ] No DKIM/sender-authenticity field was added
- [ ] `git diff --name-only` contains no file outside the in-scope list

## STOP conditions

- Making `ingest()` atomic requires changing `storage.write`'s contract or the
  `StoragePort` interface — report instead.
- The orphaned-blob question has no acceptable answer within scope.
- Adding the request id to job kwargs breaks arq's serialization for any
  existing task.
- You conclude a required (rather than optional) `message_id` is necessary for
  correctness — report; that is a Worker-coordination decision.
- Configuring logging at startup interferes with pytest's capture in a way that
  makes tests unreliable.

## Maintenance notes

- **Dedupe only engages once the Cloudflare Worker sends `message_id`.** Until
  then this plan makes ingest *atomic* but not *idempotent*. Flag that to
  whoever owns `apps/email-ingest` — it is a one-line change on their side and
  it is what makes the whole thing work.
- The sender-authenticity gap remains open and is the more serious of the two
  ingest findings: org routing still trusts an unverified `sender_email`.
- Once request ids flow, the natural follow-up is structured (JSON) logging so
  the id is a queryable field rather than text in a message.
- Reviewer should scrutinize: that the request-id middleware is registered so it
  runs before anything that logs, and that the arq kwarg is optional-with-default
  so a rolling deploy doesn't break in-flight jobs.
