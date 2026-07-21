# Plan 011: Make `make lint` actually check, and document every required env var

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- Makefile apps/backend/.env.example apps/manager/.env.example apps/backend/app/core/config.py`

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (removing the tests exclusion will surface a batch of existing violations)
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: dx
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

**`make lint` cannot fail.** It runs `ruff --fix`, `black`, and `isort` in write
mode — it rewrites the working tree and exits 0. `README.md` tells contributors
to "run `make lint` to check code style"; it does not check anything. And
because it mutates files, it can never be used as a CI gate as written.

**It also excludes the entire test suite from every linter.** All four tools
carry a tests exclusion. That is 12,418 lines of Python — comparable to the
14,823 lines of application code — with no type checking and no linting at all.
This is not theoretical: it is exactly how the six broken tests and their stale
`UserRole` imports survived on `main` (see plan 001). `ty check` reports 5
diagnostics for `app/` and 246 for the whole tree — the other 241 are hidden in
the unlinted test suite.

**Separately, `.env.example` omits the settings whose absence fails silently.**
The backend example documents 17 keys while `Settings` defines 25. The missing
ones include `RESEND_API_KEY` (without it the email channel no-ops and no
notification ever arrives — with no error) and `OPENROUTER_API_KEY` (without it
letter drafting is inert by design). A new contributor gets a working-looking
app in which two whole features quietly do nothing. On the frontend,
`VITE_API_URL` is undocumented and is a hard first-run blocker.

## Current state

The `lint` target in `Makefile` — note `--fix`, the write-mode `black`/`isort`,
and the tests exclusion on all four tools:

```make
lint: ## Run linters
	@cd apps/backend && uv run python -c "from app import *" || (echo '🚨 import failed, this means you introduced unprotected imports! 🚨'; exit 1)
	@cd apps/backend && uv run ruff check . --fix --exclude tests --exclude .venv --exclude app/alembic
	@cd apps/backend && uv run ty check . --exclude 'tests/**' --exclude '.venv/**' --exclude 'app/alembic/**'
	@cd apps/backend && uv run black . --exclude '/(tests|\.venv|app/alembic)/'
	@cd apps/backend && uv run isort . --skip tests --skip .venv --skip app/alembic
```

Measured at commit `77985cfe`:
- `uv run ruff check .` (no `--fix`, whole tree) → **3 errors**, all
  `F401 unused import`, including `UserRole` at `tests/test_worker_tasks.py:29`
- `uv run ty check app` → **5 diagnostics**
- `uv run ty check .` (whole tree) → **246 diagnostics**; the distribution is
  ~114 `invalid-argument-type`, ~76 `invalid-return-type`, ~42
  `unresolved-attribute`, plus a handful of others — almost entirely in `tests/`

The 241 test-suite diagnostics are the reason this plan is MED risk, not S:
turning `ty` on for tests in one step would produce a red gate nobody can land.

Backend settings live in `apps/backend/app/core/config.py` (25 fields on
`Settings`). Frontend env vars are read as `import.meta.env.VITE_*` across the
three apps.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Ruff check (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Ty, app only | `cd apps/backend && uv run ty check app` | current: 5 diagnostics |
| Ty, whole tree | `cd apps/backend && uv run ty check .` | current: 246 diagnostics |
| Black check | `cd apps/backend && uv run black --check .` | exit 0 |
| isort check | `cd apps/backend && uv run isort --check-only .` | exit 0 |
| Tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Count settings | `grep -c ':' apps/backend/app/core/config.py` | rough field count |
| Find VITE vars | `grep -rho 'VITE_[A-Z_]*' apps/*/src packages/*/src \| sort -u` | the true list |

## Scope

**In scope**:
- `Makefile` (the `lint` target, plus new `format` / `lint-check` targets)
- `apps/backend/.env.example`
- `apps/manager/.env.example`, `apps/investor/.env.example`, `apps/superadmin/.env.example`
- `.github/workflows/ci.yml` (wire the new checking target in — created by plan 001)
- `README.md` (only the pre-commit rules line, if the target names change)
- Python files with unused imports, **only** the minimal fixes from step 2

**Out of scope** (do NOT touch):
- **Fixing the 241 `ty` diagnostics in `tests/`.** That is a large, separate
  cleanup. This plan makes them *visible*, not resolved — see step 4.
- Any production logic change. Removing an unused import is fine; changing what
  code does is not.
- Frontend linting (ESLint/Biome) — there is none today, and adding it across
  ~23K lines is its own plan.
- Any real `.env` file. Only `.env.example` files. Never read, write, or print
  a real `.env`, and never put a real value in an example file.

## Git workflow

- Branch: `advisor/011-lint-gate-and-env`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Split mutating from checking

In the `Makefile`:

- Rename the current mutating target to `format`, keeping its behavior exactly
  (`ruff --fix`, `black`, `isort` in write mode). Contributors still need it.
- Create a new `lint` target that **checks without writing**:
  - the existing `from app import *` import smoke test (keep it — it is a good
    gate)
  - `uv run ruff check .` (no `--fix`)
  - `uv run black --check .`
  - `uv run isort --check-only .`
  - `uv run ty check app` (app only for now — see step 4)
- Keep the `.venv` and `app/alembic` exclusions everywhere. Those are correct:
  alembic migrations are generated, and `.venv` is vendored.
- **Drop the `tests` exclusion from `ruff`, `black`, and `isort`** (not yet from
  `ty` — that is step 4).

Add a `## comment` to each target so `make help` documents them.

**Verify**: `make format` still rewrites as before; `make lint` runs without modifying files — confirm with `git status --short` being empty **after** running `make lint` on a clean tree.

### Step 2: Fix what the newly-included checks surface

Run `cd apps/backend && uv run ruff check .` and fix the violations. At the time
of writing there are 3, all unused imports, including `UserRole` at
`tests/test_worker_tasks.py:29` — a leftover from the membership refactor.

Then run `uv run black --check .` and `uv run isort --check-only .` across
`tests/` and apply `make format` to fix formatting.

**Only formatting and unused-import removals.** If ruff flags something that
needs a logic change, add a scoped `# noqa: <CODE>` with a brief comment and
report it — do not change behavior in a lint-cleanup commit.

**Verify**:
- `cd apps/backend && uv run ruff check .` → exit 0
- `cd apps/backend && uv run black --check .` → exit 0
- `cd apps/backend && uv run isort --check-only .` → exit 0
- `cd apps/backend && uv run pytest -q` → 0 failures (formatting must not break tests)

### Step 3: Wire the checking target into CI

In `.github/workflows/ci.yml` (created by plan 001), replace the bare
`uv run ruff check .` step with `make lint`.

If plan 001 has not landed in your worktree, note that and skip this step rather
than creating the workflow yourself — it is plan 001's deliverable.

**Verify**: `make lint` → exit 0; the YAML still parses.

### Step 4: Record the `ty`-on-tests debt without blocking on it

Do **not** enable `ty` for `tests/` in this plan — 241 diagnostics would make
the gate permanently red.

Instead, add a `lint-strict` target that runs `uv run ty check .` (whole tree,
tests included) and is **not** wired into CI. Add a Makefile comment stating the
current diagnostic count and that the goal is to drive it to zero and then fold
it into `lint`.

This makes the debt measurable and gives the next person a one-command way to
see progress.

**Verify**: `make lint-strict` runs and reports a diagnostic count; `make lint` still exits 0.

### Step 5: Complete `apps/backend/.env.example`

Add every field defined on `Settings` in `apps/backend/app/core/config.py` that
is missing. Read the class and enumerate them — do not rely on this plan's list.
Known missing at time of writing: `RESEND_API_KEY`, `NOTIFICATION_FROM_EMAIL`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`,
`HANKO_AUDIENCE`, `DEV_STORAGE_TOKEN`, `DEBUG`.

If plan 004 has landed, also include `UPLOAD_SIGNING_SECRET`.

Group them under comment headers and, for each, mark one of:
- `# REQUIRED` — the app will not start or function without it
- `# OPTIONAL — feature disabled if unset: <which feature>` — this is the
  important category, because it is the silent-failure one. `RESEND_API_KEY`
  and `OPENROUTER_API_KEY` both belong here, and the comment should say plainly
  that email delivery / letter drafting silently do nothing without them.

**Use placeholders only. Never a real value.**

**Verify**: every field name in `Settings` appears in `.env.example` — check by listing both and diffing the name sets.

### Step 6: Complete the frontend `.env.example` files

Find the true list: `grep -rho 'VITE_[A-Z_]*' apps/*/src packages/*/src | sort -u`.

Add every variable each app actually reads to that app's `.env.example`. Known
missing from `apps/manager/.env.example`: `VITE_API_URL` (the hard blocker),
`VITE_APP_URL`, `VITE_APP_EMAIL`, `VITE_DEV_STORAGE_TOKEN`.

Give each a working local-development default where one exists (e.g. the
backend URL for local dev), since these are non-secret client-side values.

**Verify**: `grep -rho 'VITE_[A-Z_]*' apps/manager/src | sort -u` — every name appears in `apps/manager/.env.example`; repeat per app.

### Step 7: Update the README's pre-commit line

If the target names changed, update `README.md`'s "Rules before each commit"
section to reference `make lint` (checking) and mention `make format`.

If plan 010 has already rewritten the README, edit its version rather than
reverting it.

**Verify**: `grep -n 'make lint\|make format' README.md` → matches the actual target names.

## Test plan

- No new tests. The gate itself is the deliverable.
- The existing suite must pass unchanged after formatting: `cd apps/backend && uv run pytest -q` → 0 failures, same count as before.
- Behavioral check on the gate: introduce a deliberate style violation in a
  scratch file, confirm `make lint` **fails**, then remove it. A gate that
  cannot fail is the bug this plan fixes, so prove it can. Do not commit the
  scratch file.

## Done criteria

ALL must hold:

- [ ] `make lint` exits 0 **and** leaves the working tree clean (`git status --short` empty afterward)
- [ ] `make lint` exits **non-zero** when a style violation is present (verified per the test plan)
- [ ] `make format` still exists and rewrites files as the old `lint` did
- [ ] `cd apps/backend && uv run ruff check .` exits 0 with `tests/` included
- [ ] `cd apps/backend && uv run pytest -q` exits 0 with the same test count as before
- [ ] Every field on `Settings` appears in `apps/backend/.env.example`
- [ ] Every `VITE_*` variable read by each app appears in that app's `.env.example`
- [ ] No `.env.example` contains a real credential value
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- Removing the `tests` exclusion from ruff surfaces more than ~20 violations, or
  any that need a logic change rather than an import removal. Report the count
  and the categories; do not mass-edit tests to satisfy a linter.
- `black`/`isort` reformatting `tests/` causes any test to fail — that would
  mean a test depends on source formatting, which is worth reporting on its own.
- The test count changes.
- You cannot determine whether a `Settings` field is required or
  optional-but-feature-disabling. Mark it `# UNKNOWN` and report, rather than
  guessing — a wrong "REQUIRED" annotation sends contributors hunting for a
  credential they do not need.

## Maintenance notes

- **The real debt is the 241 `ty` diagnostics in `tests/`**, now measurable via
  `make lint-strict`. Driving that to zero and folding `ty` into `lint` is the
  natural follow-up. Doing it incrementally (one test module at a time) is
  realistic; doing it in one PR is not.
- The `format`/`lint` split is the convention to keep: CI runs the checking
  target, humans run the formatting one. Anything that writes files must never
  be on the CI path.
- Still absent and worth its own plan: there is **no** frontend linter. All five
  frontend packages define `"lint": "tsc --noEmit"`, which is identical to their
  `typecheck` script — so nothing catches `react-hooks/exhaustive-deps`
  violations or floating promises across ~23K lines of React.
- A reviewer should scrutinize: that `make lint` genuinely fails on a violation
  (not just that it exits 0 on clean code), and that no `.env.example` gained a
  real value.
