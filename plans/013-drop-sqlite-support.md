# Plan 013: Drop SQLite support and require PostgreSQL

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise.
>
> **Drift check (run first)**: `git diff --stat HEAD -- apps/backend/app/core apps/backend/tests/conftest.py`

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (plans 001-012 are already merged on this branch)
- **Category**: dx
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21
- **Decision**: the maintainer chose this over fixing the ~168 broken test call
  sites. Recorded in plans/README.md under "Decisions a human should confirm".

## Why this matters

The codebase advertises SQLite as the local-dev default, and that default does
not work. Measured: on SQLite the backend suite produces **168 failed / 224
passed**; on PostgreSQL it is **456 passed / 0 failed**.

The cause is that test fixtures pass plain `str` values into
`Uuid(as_uuid=True)` columns. psycopg2 coerces them; SQLite's stricter binder
raises `StatementError: 'str' object has no attribute 'hex'`. Production is
PostgreSQL, so the SQLite path is untested, unused, and actively misleading —
a new contributor following the documented setup gets a suite that is 40% red
with no explanation.

Rather than fix ~168 call sites to preserve a code path nobody runs, the
decision is to **remove SQLite support and make PostgreSQL a hard requirement
that fails loudly**. This deletes a fallback rather than adding a feature, and
it makes the documented setup match reality.

## Current state

The complete set of SQLite references (verified — this is the whole list):

`apps/backend/app/core/config.py:14` — the default DSN:
```python
    APP_DATABASE_DSN: str = "sqlite:////tmp/database.db"
```

`apps/backend/app/core/database.py:6-11` — a SQLite-only connect arg:
```python
engine = create_engine(
    settings.APP_DATABASE_DSN,
    connect_args=(
        {"check_same_thread": False} if "sqlite" in settings.APP_DATABASE_DSN else {}
    ),
)
```

`apps/backend/tests/conftest.py:30` — the fallback that silently produces the
broken configuration:
```python
    return "sqlite:////tmp/database.db"
```

`apps/backend/tests/conftest.py:36-46` — `_rewrite_to_test` has a SQLite branch
(`/tmp/database.db` → `/tmp/database_test.db`) alongside the Postgres branch.

`apps/backend/tests/conftest.py` — `_ensure_test_database()` is documented
"(Postgres only)" and early-returns for non-Postgres drivers.

`apps/backend/.env.example:15` — ships a SQLite DSN:
```
APP_DATABASE_DSN=sqlite:///var/lib/app/database.db
```

`CLAUDE.md` (Database bullet, ~line 57) — states "Defaults to SQLite for local
dev but production uses PostgreSQL (`psycopg2`)".

`README.md` — the Prerequisites section already says Postgres is required for
the test suite and describes the SQLite default as a known gap. That wording
becomes obsolete once this lands and must be simplified.

`.github/workflows/ci.yml` — already provisions a `postgres:16` service and
sets `APP_DATABASE_DSN`; no change should be needed, but verify.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | `456 passed`, 0 failed |
| Lint gate | `make lint` | exit 0 |
| Import smoke | `cd apps/backend && uv run python -c "from app import *"` | exit 0 |
| Find leftovers | `grep -rn "sqlite" --include="*.py" apps/backend/app apps/backend/tests` | no matches |

Environment for test runs (the suite needs both):
```
export APP_DOMAIN=localhost
export APP_DATABASE_DSN="$(grep '^APP_DATABASE_DSN=' /Users/andy/Developer/edenscale/apps/backend/.env | cut -d= -f2- | sed 's|/\([^/]*\)$|/taven_wt013|')"
```
Do NOT print the DSN value — it contains a password.

## Scope

**In scope**:
- `apps/backend/app/core/config.py`
- `apps/backend/app/core/database.py`
- `apps/backend/tests/conftest.py`
- `apps/backend/.env.example`
- `CLAUDE.md` (the Database bullet only)
- `README.md` (Prerequisites / Setup wording only)

**Out of scope** (do NOT touch):
- The ~168 test call sites that pass `str` into `Uuid` columns. They work fine
  under psycopg2. **Do not "fix" them** — that is the alternative approach the
  maintainer explicitly rejected, and doing both is wasted churn.
- `apps/backend/app/alembic/**`.
- `.github/workflows/ci.yml` unless verification shows it actually needs a
  change — it already uses Postgres.
- Any repository, router, service, or model.

## Steps

### Step 1: Make the DSN required with no default

In `apps/backend/app/core/config.py`, `APP_DATABASE_DSN` must no longer default
to SQLite. Prefer making it a required field (no default) so a missing value
fails at `Settings` construction with a clear pydantic error.

If a required field breaks test collection or tooling that imports `Settings`
without an env var present, fall back to keeping a default but making it a
PostgreSQL DSN pointing at localhost — and say which you chose and why.

Additionally, extend the existing `@model_validator(mode="after")` on `Settings`
(added by plans 002/004 — it is already there) to reject a DSN that does not
start with `postgresql`. The message must name `APP_DATABASE_DSN` and state
that PostgreSQL is required.

**Verify**: `cd apps/backend && uv run python -c "from app import *"` → exit 0 (with the env var set).

### Step 2: Remove the SQLite connect-args branch

In `apps/backend/app/core/database.py`, delete the conditional
`connect_args` — `check_same_thread` is a SQLite-only parameter. `create_engine`
should be called with just the DSN (plus any non-SQLite args already present).

**Verify**: `grep -n "sqlite\|check_same_thread" apps/backend/app/core/database.py` → no matches.

### Step 3: Remove the conftest fallback and SQLite branch

In `apps/backend/tests/conftest.py`:

- `_load_env_dsn()` must **raise** instead of returning the SQLite fallback when
  no DSN is configured. Raise a `RuntimeError` whose message says PostgreSQL is
  required, names `APP_DATABASE_DSN`, and tells the reader to set it or copy
  `.env.example`. A loud failure at collection time is the whole point — a
  contributor must never again get a silently-broken 168-failure run.
- `_rewrite_to_test()` — delete the SQLite branch; keep only the Postgres
  `<db>` → `<db>_test` rewrite.
- `_ensure_test_database()` — drop the "Postgres only" early return and the
  now-dead driver check; it can assume Postgres.

Keep the existing `SUPERADMIN_EMAIL` / `RESEND_API_KEY` env overrides exactly
as they are.

**Also add** `os.environ["APP_DOMAIN"] = "localhost"` alongside those overrides.
This is a separate small fix identified during plan 002: the `Settings`
validator refuses to construct when `APP_DOMAIN` is non-localhost and `DEBUG`
is false, which makes the suite fail in any environment without a `.env` (CI,
git worktrees). Setting it in conftest makes the suite self-contained. Comment
it accordingly.

**Verify**: `cd apps/backend && uv run pytest -q` → `456 passed`, 0 failed.

### Step 4: Update `.env.example`

Replace the SQLite DSN at `apps/backend/.env.example:15` with a PostgreSQL
placeholder, e.g.:
```
APP_DATABASE_DSN=postgresql://postgres:postgres@localhost:5432/taven
```
Keep the REQUIRED/OPTIONAL annotation convention already established in that
file (added by plan 011). Mark this one REQUIRED and note that the test suite
appends `_test` to the database name automatically.

**Never put a real credential in this file** — placeholders only.

**Verify**: `grep -n "sqlite" apps/backend/.env.example` → no matches.

### Step 5: Update the docs

`CLAUDE.md` — the Database bullet currently says it "Defaults to SQLite for
local dev but production uses PostgreSQL". Replace with a statement that
PostgreSQL is required in all environments and that a missing/non-Postgres
`APP_DATABASE_DSN` fails at startup. Change nothing else in that file.

`README.md` — the Prerequisites section currently describes the SQLite default
as a known-broken gap (added by plan 010). That caveat is now obsolete:
simplify to "PostgreSQL is required" and drop the explanation about the
168-failure divergence, since the divergence no longer exists. Keep the note
that the suite uses a `_test` sibling database.

**Verify**: `grep -rn "sqlite" CLAUDE.md README.md` → no matches (case-insensitive check too).

### Step 6: Confirm CI needs no change

Read `.github/workflows/ci.yml`. It should already provision `postgres:16` and
set `APP_DATABASE_DSN`. Confirm it also sets `APP_DOMAIN=localhost` **or** that
step 3's conftest change makes that unnecessary — one or the other must be true,
or CI fails on `Settings` construction.

Report what you found. Only change the workflow if it is genuinely broken.

**Verify**: state in your report which mechanism covers `APP_DOMAIN` in CI.

## Test plan

- No new tests. The deliverable is the removal of a broken code path.
- The existing 456 tests must all still pass — they already run on Postgres.
- **Behavioral check**: confirm the new failure is loud. Temporarily unset
  `APP_DATABASE_DSN` (in a subshell, with no `.env` visible) and confirm the
  suite fails fast with your clear message rather than silently running on
  SQLite. Report the observed message. Do not leave anything modified.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` → `456 passed`, 0 failed
- [ ] `make lint` exits 0
- [ ] `cd apps/backend && uv run python -c "from app import *"` exits 0
- [ ] `grep -rn "sqlite" --include="*.py" apps/backend/app apps/backend/tests` → no matches
- [ ] `grep -rni "sqlite" CLAUDE.md README.md apps/backend/.env.example` → no matches
- [ ] A missing `APP_DATABASE_DSN` produces a clear, immediate error naming the variable
- [ ] `conftest.py` sets `APP_DOMAIN=localhost` alongside its other env overrides
- [ ] No test call site was changed (`git diff --stat apps/backend/tests/` shows only `conftest.py`)
- [ ] `git diff --name-only` contains no file outside the in-scope list

## STOP conditions

Stop and report back (do not improvise) if:

- Making `APP_DATABASE_DSN` required breaks something you cannot resolve by
  falling back to a Postgres default (step 1 allows that fallback — take it and
  report, rather than stopping, unless something else breaks).
- Any of the 456 tests fails after your changes.
- You find a SQLite reference outside the list in "Current state" that looks
  load-bearing — report it rather than deleting it.
- You find yourself editing a test file other than `conftest.py`.

## Maintenance notes

- This closes the divergence recorded in plans/README.md's deferred list. Once
  merged, remove that entry (the advisor maintains that file).
- The `str`-into-`Uuid` pattern in ~168 test call sites still exists and is now
  permanently masked by psycopg2's coercion. It is not a bug under Postgres, but
  it is sloppy and would resurface instantly if anyone ever tried another
  driver. Worth a low-priority cleanup someday; explicitly not now.
- A reviewer should scrutinize: that the failure mode for a missing DSN is loud
  and clear (that is the entire point of the change), and that no test call site
  was "fixed" as a side effect.
