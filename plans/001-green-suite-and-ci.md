# Plan 001: Make `make test` green and gate every push with CI

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/tests .github/workflows package.json Makefile`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests | dx
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

The backend test suite is currently **red on `main`**: 6 of 392 tests fail. They
fail because they were never updated when the membership refactor landed
(commit `995610d4` "drop legacy users.organization_id, make membership the
source of truth") — they still construct users with a `role=` and
`organization_id=` that no longer exist on the model.

Nothing caught this because **no CI runs the tests**. Both workflows in
`.github/workflows/` are disabled with `if: false`, and no workflow runs pytest
or lint on push or PR. `README.md:16-20` instructs contributors to run
`make test` before committing; that is an unenforced convention, and it has
already been violated on `main`.

Every other plan in `plans/` changes money-handling or auth code and states
"`make test` passes" in its done criteria. That criterion is meaningless while
the baseline is red — an executor cannot distinguish "I broke something" from
"it was already broken". **This plan must land before any other.**

## Current state

Running `cd apps/backend && uv run pytest -q` at commit `77985cfe` produces:

```
6 failed, 386 passed in 38.76s
FAILED tests/test_invitations_router.py::TestCreateInvitation::test_superadmin_can_invite_into_any_org
FAILED tests/test_invitations_router.py::TestCreateInvitation::test_404_when_organization_missing
FAILED tests/test_organizations_api.py::TestLegacyOrganizationMutationsRemoved::test_superadmin_must_use_superadmin_create_route
FAILED tests/test_organizations_api.py::TestLegacyOrganizationMutationsRemoved::test_admin_cannot_create
FAILED tests/test_organizations_api.py::TestLegacyOrganizationMutationsRemoved::test_lp_cannot_create
FAILED tests/test_organizations_api.py::TestListAndReadOrganization::test_fund_manager_can_read
```

A representative failure, `tests/test_organizations_api.py:222`:

```python
    def test_fund_manager_can_read(self, client, override_user):
        org_id = _seed_org()
        _seed_user(
            "hanko-fm",
            UserRole.fund_manager,
            email="fm@example.com",
            organization_id=org_id,          # <-- column no longer exists
        )
        override_user("hanko-fm")

        list_response = client.get("/organizations")
        assert list_response.status_code == 405     # <-- actual: 404
```

The model these tests assume is gone. `apps/backend/app/models/user.py` has
**no** `role` column and **no** `organization_id` column. Roles live on
`apps/backend/app/models/user_organization_membership.py`, and superadmin is a
derived property, `apps/backend/app/models/user.py:64-70`:

```python
    @property
    def is_superadmin(self) -> bool:
        """Superadmins are defined by ``SUPERADMIN_EMAIL`` in config, never
        stored: a user is a superadmin iff their (Hanko-verified) email is
        listed there. Per-organization roles live on memberships."""
        return (self.email or "").lower() in settings.superadmin_emails
```

**These tests assert on removed behavior, not on broken behavior.** The
`TestLegacyOrganizationMutationsRemoved` class exists to prove that
`POST /organizations` returns `405 Method Not Allowed`; the route now returns
`404`, because the route was deleted outright rather than replaced with a
method-restricted one. That is the *intended* end state — superadmin org
creation moved to `app/routers/superadmin.py`. So the tests' *intent* is still
valid ("a non-superadmin cannot create an org this way"); only their expected
status code and their seeding helpers are stale.

Test conventions to match — see `apps/backend/tests/conftest.py` for the
`client` and `override_user` fixtures, and
`apps/backend/tests/test_membership_repository.py` for the **current** way to
seed a user with an org role (membership rows, not user columns). Model your
edits on that file.

Also note for step 4: the two frontend test files
(`apps/manager/src/lib/managerRoutes.test.ts`,
`apps/investor/src/lib/investorRoutes.test.ts`) are run by **no** command —
root `package.json` has no `test` script even though `turbo.json` defines a
`test` task and each app declares `"test": "vitest run"`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | `392 passed` (0 failed) |
| One test file | `cd apps/backend && uv run pytest tests/test_organizations_api.py -v` | all pass |
| Backend lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Frontend tests | `pnpm turbo run test` | all pass |
| Frontend typecheck | `pnpm turbo run typecheck` | exit 0 |

Note: do **not** use `make lint` as a verification gate in this plan. It runs
`ruff --fix`, `black`, and `isort` in write mode and rewrites files; it cannot
fail. Plan 011 splits it into a checking variant. Use `ruff check .` here.

## Scope

**In scope** (the only files you should modify):
- `apps/backend/tests/test_organizations_api.py`
- `apps/backend/tests/test_invitations_router.py`
- `apps/backend/tests/test_bank_imports_api.py` (step 2b — remove one unused import)
- `apps/backend/tests/test_membership_repository.py` (step 2b — remove one unused import)
- `apps/backend/tests/test_worker_tasks.py` (step 2b — remove one unused import)
- `.github/workflows/ci.yml` (create)
- `package.json` (root — add a `test` script only)

**Out of scope** (do NOT touch, even though they look related):
- `apps/backend/app/**` — this plan changes **no production code**. The 6
  failures are stale test expectations, not app bugs. If you conclude an app
  file must change to make a test pass, that is a STOP condition.
- `.github/workflows/deploy.yml` and `docker-image.yml` — both are
  intentionally `if: false`. Re-enabling deployment is a separate decision with
  production consequences; leave both exactly as they are.
- `Makefile` — the `lint` target's mutating behavior is plan 011's job.
- Any other failing-looking test — only these 6 are failing.

## Git workflow

- Branch: `advisor/001-green-suite-and-ci`
- Commit per step. Message style is plain imperative sentences (see
  `git log --oneline`, e.g. `rename`, `update workspace`, `web manifests`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Fix the 4 failures in `test_organizations_api.py`

Read the whole file first, plus `apps/backend/tests/test_membership_repository.py`
for the current seeding idiom.

For `TestLegacyOrganizationMutationsRemoved` (3 tests): the assertion
`status_code == 405` must become `status_code == 404`. The route
`POST /organizations` no longer exists at all — confirm this yourself by
grepping: `grep -n 'post' apps/backend/app/routers/organizations.py`. Keep each
test's intent and name; update the expected code and add a short comment
explaining the route was removed in favor of `app/routers/superadmin.py`.

For `test_fund_manager_can_read`: rewrite `_seed_user` usage so the user's role
comes from a membership row rather than `role=`/`organization_id=` kwargs.
Update the module-level `_seed_user` helper if the other tests in the file share
it — check whether the helper already supports memberships before adding a
second one.

**Verify**: `cd apps/backend && uv run pytest tests/test_organizations_api.py -v` → all pass.

### Step 2: Replace the 2 obsolete tests in `test_invitations_router.py`

**This step was corrected after a first execution attempt. It is NOT the same
root cause as step 1 — do not apply the step 1 fix shape here.**

These two tests (`test_superadmin_can_invite_into_any_org`,
`test_404_when_organization_missing`) seed their users correctly already. They
fail with `403` because commit `735395bc` added a router-level
`Depends(require_tenant_user)` to `app/routers/invitations.py`, and
`app/core/rbac.py:76-86` unconditionally rejects superadmins:

```python
def require_tenant_user(
    current_user: User = Depends(get_current_user_record),
) -> User:
    """Reject platform administrators from tenant-only, non-membership flows."""
    if current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmins must use /superadmin endpoints",
        )
```

`grep -n "invit" apps/backend/app/routers/superadmin.py` returns **nothing** —
there is no superadmin invitation route. Superadmins assign memberships directly
via `assign_organization_admin`, bypassing invitations entirely. So the
capability these tests assert **was deliberately removed**, and the removal is
confirmed by that commit's own message.

**The decision has been made: the removal is intentional. Do not restore the
capability.** Rewrite the two tests to pin the new behavior:

- `test_superadmin_can_invite_into_any_org` → rename to
  `test_superadmin_cannot_invite_and_must_use_superadmin_routes`, assert `403`,
  and add a comment naming `require_tenant_user` and pointing at
  `app/routers/superadmin.py` as the supported path. This converts a test of a
  dead capability into a test that the access-control boundary holds — which is
  worth having.
- `test_404_when_organization_missing` → the 404 path is no longer reachable by
  a superadmin. Re-seat it on a **tenant admin** so it still exercises the
  missing-organization branch. If you determine that branch is unreachable for
  any non-superadmin caller (because a tenant admin's membership implies the org
  exists), then delete the test and say so explicitly in your report, naming the
  reason — do not leave a test that passes for the wrong reason.

**Verify**: `cd apps/backend && uv run pytest tests/test_invitations_router.py -v` → all pass.

### Step 2b: Clear the 3 pre-existing ruff errors

**Added after a first execution attempt** — `uv run ruff check .` is **not**
clean at this plan's commit, so CI would fail on arrival without this step.

There are exactly 3 errors, all `F401 unused import`, all in test files, all
one-line deletions:
- `tests/test_bank_imports_api.py` — unused `uuid`
- `tests/test_membership_repository.py` — unused `UserOrganizationMembership`
- `tests/test_worker_tasks.py:29` — unused `UserRole` (more membership-refactor debris)

Delete those three imports. Nothing else — the broader lint cleanup, and making
`make lint` a real gate, belong to plan 011.

**Verify**: `cd apps/backend && uv run ruff check .` → exit 0.

### Step 3: Confirm the whole suite is green

**Verify**: `cd apps/backend && uv run pytest -q` → `392 passed`, 0 failed.

If any test outside the 6 listed above now fails, STOP — you have changed
shared helper behavior.

### Step 4: Add a root `test` script

Add to root `package.json` scripts: `"test": "turbo run test"`.

**Verify**: `pnpm run test` → runs vitest in `apps/manager` and `apps/investor`, both pass.

### Step 5: Add the CI workflow

Create `.github/workflows/ci.yml` that runs on `push` and `pull_request` (no
branch filter — every push). It needs two jobs:

`backend`:
- `actions/checkout@v5`
- Install `uv` (`astral-sh/setup-uv@v5`), Python 3.12
- Service container `postgres:16` with a healthcheck; set `APP_DATABASE_DSN` to
  point at it. `apps/backend/tests/conftest.py` rewrites the DSN to a sibling
  `_test` database — read it before writing the job so you match that
  convention.

  **Postgres is mandatory. Do not let CI fall back to SQLite.** `conftest.py:30`
  defaults to `sqlite:////tmp/database.db` when no DSN is configured, and the
  suite **does not work on SQLite**: measured at this plan's commit, SQLite
  yields `168 failed, 224 passed`, versus `2 failed, 390 passed` on Postgres.
  (The cause is test helpers passing `str` where a `Uuid(as_uuid=True)` column
  is declared — psycopg2 coerces it, SQLite's stricter binder rejects it.) A CI
  job without the Postgres service would be permanently and confusingly red.
- `cd apps/backend && uv sync`
- `cd apps/backend && uv run pytest -q`
- `cd apps/backend && uv run ruff check .`

`frontend`:
- `actions/checkout@v5`, `pnpm/action-setup@v4`, `actions/setup-node@v4` with
  pnpm cache
- `pnpm install --frozen-lockfile`
- `pnpm turbo run typecheck`
- `pnpm turbo run test`

Do **not** add a deploy step, and do **not** touch the two disabled workflows.

**Verify**: `cd apps/backend && uv run pytest -q && uv run ruff check .` passes
locally, and the YAML parses:
`python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` → exit 0.

## Test plan

- No new test *cases* are required — this plan repairs existing ones.
- Do not delete any of the 6 tests. Each asserts a real behavior
  (non-superadmins cannot create orgs; a fund manager can read their org). If
  you believe a test is genuinely obsolete rather than stale, STOP and report
  which one and why, rather than deleting it.
- Use `apps/backend/tests/test_membership_repository.py` as the structural
  pattern for membership-based seeding.
- Verification: `cd apps/backend && uv run pytest -q` → 392 passed.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `pnpm run test` exits 0 and runs both frontend test files
- [ ] `pnpm turbo run typecheck` exits 0
- [ ] `.github/workflows/ci.yml` exists, triggers on `push` and `pull_request`, and parses as valid YAML
- [ ] `grep -rn "organization_id=" apps/backend/tests/test_organizations_api.py apps/backend/tests/test_invitations_router.py` returns no matches passing it to a `User` constructor
- [ ] `git diff --name-only` shows **no** files under `apps/backend/app/`
- [ ] `.github/workflows/deploy.yml` and `docker-image.yml` are unmodified (`git diff --name-only` excludes both)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The suite shows a different set of failures than the 6 listed above (the
  codebase drifted since this plan was written).
- Making a test pass appears to require editing anything under
  `apps/backend/app/` — that means the finding was misdiagnosed and a real app
  bug exists; report it rather than fixing it here.
- More than the 6 listed tests fail after your changes.
- `conftest.py` turns out to require a database configuration you cannot
  reproduce in CI — report what it needs instead of guessing at a service
  container config.

## Maintenance notes

- Once CI is green, the `if: false` on the two deploy workflows becomes the
  next decision to make deliberately — it is **out of scope here** and should
  be a conscious choice by the operator, not a side effect.
- The CI workflow runs `ruff check` but not `ty check`, because `ty` currently
  reports 246 diagnostics repo-wide (241 of them in `tests/`, which every
  linter excludes today). Plan 011 addresses that; adding `ty` to CI before
  then would make CI permanently red.
- Reviewer should scrutinize: that no production code changed, and that the
  three `405 → 404` edits kept each test's original intent rather than being
  weakened to pass.
