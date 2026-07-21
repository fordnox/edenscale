# Plan 006: Stop blocking the event loop on synchronous database calls

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/routers apps/backend/app/core/database.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M (mechanical but touches many files)
- **Risk**: MED (broad blast radius; individually trivial edits)
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: perf
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

This is the single largest throughput ceiling in the backend.

FastAPI runs `async def` route handlers on the main event loop, and plain `def`
handlers in a threadpool. This codebase declares almost every route `async def`
— but the database layer is entirely **synchronous** (SQLAlchemy with
psycopg2). So every DB-touching handler performs blocking socket I/O directly on
the event loop.

The consequence: the whole process serializes. One slow dashboard query stalls
*every* concurrent request, including health checks. Effective backend
concurrency is one request per worker, regardless of connection-pool size.

The fix is close to a one-word edit per handler: dropping `async` moves the
handler into FastAPI's threadpool, where blocking I/O belongs. This captures
most of the available win for a fraction of the risk of a full async-SQLAlchemy
migration (which would be an L-effort, high-risk project touching every
repository — explicitly **not** what this plan does).

## Current state

`apps/backend/app/core/database.py:6-22` — a synchronous engine and session:

```python
engine = create_engine(
    settings.APP_DATABASE_DSN,
    connect_args=(
        {"check_same_thread": False} if "sqlite" in settings.APP_DATABASE_DSN else {}
    ),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

There is **no** async engine anywhere in the tree — confirm with
`grep -rn 'create_async_engine\|AsyncSession' apps/backend/app` (expect no matches).

A representative handler, `apps/backend/app/routers/investors.py:57-70`:

```python
@router.get("", response_model=list[InvestorListItem])
async def list_investors(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = InvestorRepository(db)
    rows = repo.list_for_membership(membership, skip=skip, limit=limit)
    return [
        _to_list_item(investor, total_committed, fund_count)
        for investor, total_committed, fund_count in rows
    ]
```

No `await` in the body — this handler gains nothing from being `async` and pays
the full serialization cost.

Approximate `async def` counts per router file (from
`grep -c "async def" apps/backend/app/routers/*.py`): investor_portal 14,
superadmin 11, documents 10, capital_calls 9, distributions 9, communications 8,
commitments 7, funds 7, invitations 6, tasks 6, users 6, fund_groups 5,
organizations 5, investors 5, bank_imports 4, investor_contacts 4,
notifications 4, fund_valuations 3, audit_logs 1, dashboard 1, email_ingest 1.

**Handlers that genuinely `await`** and must stay `async` — these are the
exceptions the plan is really about:
- `apps/backend/app/routers/bank_imports.py:106` — `await file.read()`
- `apps/backend/app/routers/documents.py:163` — `await request.body()`
- `apps/backend/app/routers/documents.py` dev-storage routes — `await request.body()`
- Any handler awaiting an `enqueue_*` helper from `app/tasks.py`
- Any handler awaiting a `notify_*` / `publish_*` helper

Find them all with:
`grep -rn "await " apps/backend/app/routers/` — that list is authoritative, not
the examples above.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Import smoke test | `cd apps/backend && uv run python -c "from app import *"` | exit 0 |
| Find awaits | `grep -rn "await " apps/backend/app/routers/` | the authoritative exception list |
| Regenerate client | `make openapi` | exit 0 |

## Scope

**In scope**:
- `apps/backend/app/routers/*.py` — handler signatures only
- `apps/backend/tests/` — only if a test asserts on handler coroutine-ness (unlikely)

**Out of scope** (do NOT touch):
- `apps/backend/app/core/database.py` — no async engine. This plan explicitly
  does **not** migrate to async SQLAlchemy.
- `apps/backend/app/repositories/**` and `apps/backend/app/services/**` — no
  changes. If you find yourself editing a repository, you have exceeded scope.
- `apps/backend/app/worker.py` and `app/tasks.py` — arq tasks are genuinely
  async and stay that way.
- Handler **bodies**. This plan changes the `async` keyword and, where required,
  wraps a call in `run_in_threadpool`. It changes no business logic.
- Dependency functions (`get_db`, `get_active_membership`, etc.) — unchanged.

## Git workflow

- Branch: `advisor/006-unblock-event-loop`
- **Commit per router file**, so a regression can be bisected to one file.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Build the exception list

Run `grep -rn "await " apps/backend/app/routers/` and write down every handler
that contains an `await` in its body. These handlers **keep** `async def`.

Every other handler in `apps/backend/app/routers/*.py` is a conversion
candidate.

**Verify**: you have a written list before editing anything.

### Step 2: Convert one router as a pilot

Start with `apps/backend/app/routers/investors.py` (5 handlers, no awaits, well
covered by `tests/test_investors_api.py`).

Remove the `async` keyword from every handler in the file that is not on the
step-1 exception list. Change nothing else.

**Verify**: `cd apps/backend && uv run pytest tests/test_investors_api.py -v` → all pass.

### Step 3: Convert the remaining routers, one file per commit

Work through the rest. For each file: remove `async` from non-excepted
handlers, then run that file's test module before moving on.

Map of router → test module (verify by listing `apps/backend/tests/`):
`funds.py`→`test_funds_api.py`, `commitments.py`→`test_commitments_api.py`,
`capital_calls.py`→`test_capital_calls_api.py`,
`distributions.py`→`test_distributions_api.py`,
`documents.py`→`test_documents_api.py`,
`communications.py`→`test_communications_api.py`,
`tasks.py`→`test_tasks_api.py`, `users.py`→`test_users_api.py`,
`organizations.py`→`test_organizations_api.py`,
`notifications.py`→`test_notifications_api.py`,
`invitations.py`→`test_invitations_router.py`,
`superadmin.py`→`test_superadmin_routes.py`,
`investor_portal.py`→`test_investor_portal.py`,
`bank_imports.py`→`test_bank_imports_api.py`,
`fund_valuations.py`→`test_fund_valuations.py`,
`dashboard.py`→`test_dashboard.py`,
`audit_logs.py`→`test_audit_log.py`,
`email_ingest.py`→`test_email_ingest.py`.
`fund_groups.py` and `investor_contacts.py` may have no dedicated module — run
the full suite for those.

**Verify** after each file: that file's test module passes.

### Step 4: Handle the mixed handlers

For handlers on the exception list that `await` something *and* also make
blocking repository calls (`bank_imports.py:106` is the clearest case — it
awaits `file.read()` and then parses and writes to the DB): keep `async def`,
and wrap the **blocking** portion in
`starlette.concurrency.run_in_threadpool`.

Do this only where the blocking work is substantial (a parse, a multi-write
transaction). For a handler that awaits an enqueue and does one small query, the
benefit does not justify the churn — leave it and note it.

Be careful: `run_in_threadpool` takes a callable, so wrap
`lambda: repo.method(args)` or use `functools.partial`. Getting this wrong
silently passes a coroutine or calls the function eagerly.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 5: Full verification

**Verify**:
- `cd apps/backend && uv run pytest -q` → 0 failures
- `cd apps/backend && uv run ruff check .` → exit 0
- `cd apps/backend && uv run python -c "from app import *"` → exit 0
- `make openapi` → exit 0, and `git diff --stat apps/backend/openapi.json`
  shows **no change** (removing `async` must not alter the OpenAPI schema — if
  it does, something else changed and you should investigate)

## Test plan

- No new tests. The existing 392-test suite is the safety net, and it exercises
  every router through `TestClient`.
- The suite must pass at **exactly** the pre-change count. A test that
  disappears or is skipped is a red flag.
- If any test was written to `await` a handler function directly (rather than
  going through `TestClient`), it will break — fix the test to call through the
  client, and report that you did.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures and the same
      total test count as before the change
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `cd apps/backend && uv run python -c "from app import *"` exits 0
- [ ] `make openapi` produces **no diff** in `apps/backend/openapi.json`
- [ ] Every remaining `async def` in `apps/backend/app/routers/` either contains
      an `await` in its body or is documented in your report as a deliberate
      exception — verify by re-running the step-1 grep and comparing
- [ ] `git diff --name-only` shows only files under `apps/backend/app/routers/`
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- Any test fails after converting a router and the cause is not obvious within
  one fix attempt — revert that file and report which one.
- `make openapi` produces a diff.
- You find a handler that awaits something whose blocking/async nature you
  cannot determine by reading it.
- A dependency (not a handler) turns out to be `async def` while doing blocking
  work — that is a real finding but a different fix; report it rather than
  changing dependency signatures.
- The total test count changes.

## Maintenance notes

- **The rule to enforce going forward**: a route handler in this codebase should
  be `def`, not `async def`, unless its body contains `await`. Worth adding to
  `CLAUDE.md`'s backend coding rules, and worth a lint check — a small test that
  walks the router modules and asserts no `async def` handler takes
  `Depends(get_db)` without a `run_in_threadpool` call would prevent regression.
  That test is a reasonable follow-up, not part of this plan.
- The threadpool has a default size (40 in AnyIO). Under real load that becomes
  the new concurrency limit and may need tuning alongside the DB pool size,
  which is currently unconfigured in `create_engine`.
- The full async-SQLAlchemy migration remains available later. It would require
  psycopg3, `AsyncSession`, and converting all 164 legacy `.query(...)` call
  sites to `select()` — a large project whose value should be re-measured
  *after* this plan lands, since this captures most of the throughput win.
- A reviewer should scrutinize: every handler that kept `async def`, confirming
  it genuinely awaits; and every `run_in_threadpool` call, confirming it wraps a
  callable rather than invoking it eagerly.
