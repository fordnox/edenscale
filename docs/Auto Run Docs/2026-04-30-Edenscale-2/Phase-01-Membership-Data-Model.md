# Phase 01: Per-Org Memberships + Superadmin Foundation

This phase lays the data-model foundation for multi-org membership and global superadmins. By the end of the phase the backend will compile, `make lint` / `make test` / `make openapi` will pass, a brand-new `user_organization_memberships` table will exist, the `superadmin` role will be live in the enum, every existing user with a non-null `users.organization_id` will be backfilled into a membership row, and a `python -m app.scripts.promote_superadmin <email>` CLI will let you flip a row to superadmin from a shell. No frontend changes yet — this is the bedrock everything else stands on.

## Tasks

- [x] Read the orientation files before touching anything else so the generated code blends with project conventions:
  - `CLAUDE.md`, `backend/app/main.py`, `backend/app/core/rbac.py`, `backend/app/core/auth.py`
  - `backend/app/models/user.py`, `backend/app/models/organization.py`, `backend/app/models/enums.py`
  - One existing model + repository + schema + router quartet (e.g. `fund_group.py`) to mirror the layering style
  - `backend/app/alembic/versions/20260429_2310_d496f70bae71_initial_schema_from_dbml.py` to copy the alembic style (server defaults, enum creation pattern)

  **Orientation notes (for subsequent tasks):**
  - `UserRole` is `str, enum.Enum` with values `admin / fund_manager / lp` — adding `superadmin` as the FIRST member preserves existing ordinal/string values.
  - Models follow the SQLAlchemy `Column(...)` declarative style with `server_default=func.now()` for `created_at`/`updated_at`, `index=True` on FKs, and bidirectional `relationship(..., back_populates=...)`. New models must be imported somewhere reachable from app startup so `Base.metadata` registers them — the existing approach is implicit imports via `app/main.py` -> `routers/` -> `repositories/` -> `models/`.
  - Repositories take a `Session` in `__init__`, expose explicit `list_*/get/create/update/delete` methods, and `commit()` + `refresh()` after writes (see `UserRepository`, `FundGroupRepository`).
  - Schemas use Pydantic v2 with `ConfigDict(from_attributes=True)`. `UserRead` currently exposes `organization_id` directly — keep it readable when adding `memberships`.
  - The auth pipeline is: Hanko JWT → `get_current_user` (decoded payload dict) → `get_current_user_record` (resolves/creates local `User` row) → `require_roles(...)` factory. New `superadmin` role must be added to allow-lists where it should bypass org scoping.
  - The initial migration uses native PG enum types created implicitly by `sa.Enum(..., name=...)` and uses `sa.text('(CURRENT_TIMESTAMP)')` for SQLite-friendly server defaults. Postgres enum value additions need `ALTER TYPE ... ADD VALUE`; SQLite uses CHECK constraints so the existing `user_role` CHECK must be recreated to include `superadmin` (or the dialect branch should no-op since SQLite stores it as a VARCHAR with a CHECK constraint via `sa.Enum`).
  - Down-revision chain: latest is `d496f70bae71` (initial dbml schema).

- [x] Extend the `UserRole` enum and create the membership ORM model:
  - In `backend/app/models/enums.py`, add `superadmin = "superadmin"` as the FIRST member of `UserRole` (keep order stable for existing values)
  - Create `backend/app/models/user_organization_membership.py` with a `UserOrganizationMembership(Base)` class: `__tablename__ = "user_organization_memberships"`; columns `id` (PK), `user_id` (FK `users.id`, indexed), `organization_id` (FK `organizations.id`, indexed), `role` (Enum `UserRole`, name `"membership_role"`, NOT NULL), `created_at` and `updated_at` mirroring `User`. Add a `UniqueConstraint("user_id", "organization_id", name="uq_user_org_membership")`.
  - Add SQLAlchemy `relationship` back-references on both sides: `User.memberships` and `Organization.memberships`, both `back_populates="user"` / `back_populates="organization"` respectively
  - Register the new model so it gets imported on app startup (it must be imported by `app/__init__.py` or a model-aggregator so `Base.metadata` sees it — check how the other models are wired)

- [x] Add the Pydantic schemas for memberships:
  - Create `backend/app/schemas/user_organization_membership.py` with `MembershipBase` / `MembershipCreate` / `MembershipUpdate` / `MembershipRead` following the style of `schemas/user.py`. `MembershipRead` should include nested `organization: OrganizationRead` and `role: UserRole` so the frontend can render the org switcher off a single endpoint
  - Update `schemas/user.py` `UserRead` to include an optional `memberships: list[MembershipRead] = []` field — but DO NOT remove `organization_id` yet (the migration to drop it lands later; keep both readable for now). Use a forward-ref / late import to avoid circular imports.

  **Implementation notes:**
  - Created `backend/app/schemas/user_organization_membership.py` with `MembershipBase`, `MembershipCreate`, `MembershipUpdate`, `MembershipRead`. `MembershipRead` exposes `id`, `user_id`, `organization_id`, `role: UserRole`, nested `organization: OrganizationRead`, `created_at`, `updated_at` with `ConfigDict(from_attributes=True)`.
  - `MembershipUpdate` exposes only `role` (matches the repository's `update_role` operation in the next task; create/delete aren't field updates).
  - Updated `UserRead` with `memberships: list[MembershipRead] = []` — kept `organization_id` as instructed. No circular import needed because `MembershipRead` imports from `organization` only, not `user`.
  - Wired the new schemas into `app/schemas/__init__.py` for parity with the rest of the aggregator. Verified `from app.schemas.user import UserRead` resolves and `model_json_schema()` renders both refs cleanly.

- [x] Build the membership repository:
  - Create `backend/app/repositories/user_organization_membership_repository.py` mirroring the style of `repositories/user_repository.py`
  - Methods: `list_for_user(user_id)`, `list_for_organization(organization_id)`, `get(user_id, organization_id)`, `create(user_id, organization_id, role)`, `update_role(membership_id, role)`, `delete(membership_id)`, `bulk_seed_from_legacy_user_org_id()` — the bulk method idempotently creates memberships for every `User.organization_id is not None` that doesn't already have a row

  **Implementation notes:**
  - Created `backend/app/repositories/user_organization_membership_repository.py` following the `UserRepository` style: `Session` injected via `__init__`, explicit list/get/create/update/delete methods, `commit()` + `refresh()` after writes.
  - `bulk_seed_from_legacy_user_org_id()` walks every user with a non-null `organization_id`, calls `get(user_id, organization_id)` to skip rows that already exist, copies `User.role` onto the new membership, and only commits when at least one row was added (returning the insert count for callers/tests). This keeps repeated runs idempotent — required by the migration backfill and by the test the next task adds.
  - Wired the new class into `backend/app/repositories/__init__.py` alongside `UserRepository` so the aggregator stays consistent.

- [x] Author the alembic migration that adds the new schema:
  - Run `cd backend && uv run alembic revision -m "add user_organization_memberships and superadmin role" --autogenerate` (or hand-write if autogenerate misses the enum value addition — Postgres needs `ALTER TYPE user_role ADD VALUE 'superadmin'`)
  - The `upgrade()` must:
    1. Add `'superadmin'` to the existing `user_role` enum type (use `op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'superadmin'")` for Postgres; SQLite uses CHECK so just recreate the table — guard with `op.get_bind().dialect.name`)
    2. Create the `membership_role` enum type with all four values
    3. Create the `user_organization_memberships` table with FKs, unique constraint, and timestamp defaults
    4. Backfill: insert one membership row for every existing `users.organization_id is not null`, with `role` copied from `users.role` and `created_at = now()`
  - The `downgrade()` must drop the table and the enum type (do NOT downgrade the user_role enum value — that's a one-way door in PG; document this in a one-line comment)
  - Run `make upgrade` against the local SQLite DB and confirm it applies cleanly

  **Implementation notes:**
  - Generated `backend/app/alembic/versions/20260430_2257_ee0cff22bcfc_add_user_organization_memberships_and_.py` via `alembic revision --autogenerate`, then hand-edited it to add the dialect branch, the `membership_role` enum implicitly via `sa.Enum`, the backfill `INSERT ... SELECT`, and an explicit `DROP TYPE IF EXISTS membership_role` on Postgres downgrade.
  - For the `user_role` enum extension: `bind.dialect.name == "postgresql"` runs `ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'superadmin'`. The SQLite branch is a deliberate no-op — verified by reading `sqlite_master` for the existing `users` table; SQLAlchemy 2.x's `sa.Enum` rendered the column as plain `VARCHAR(12)` with no CHECK constraint, so SQLite already accepts any 12-char string (and `superadmin` is 10 chars).
  - Backfill uses `INSERT INTO user_organization_memberships (user_id, organization_id, role, created_at, updated_at) SELECT id, organization_id, role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users WHERE organization_id IS NOT NULL`. Verified end-to-end: `make upgrade` → 7 rows inserted on local SQLite (matching the seeded users with non-null org), `make downgrade` → table dropped cleanly, second `make upgrade` → re-applies cleanly with the same 7 rows.
  - Down-revision chained off `d496f70bae71`. Downgrade documents the deliberate non-removal of the `user_role` 'superadmin' value with a one-line comment (PG enum value removal is a one-way door).

- [x] Add a CLI to manually promote a user to superadmin (since superadmin assignment is intentionally out-of-band):
  - Create `backend/app/scripts/__init__.py` and `backend/app/scripts/promote_superadmin.py` with a `main()` that takes `email` as a positional CLI arg, opens a session via `app.core.database.SessionLocal`, finds the user by email, sets `user.role = UserRole.superadmin` and `user.organization_id = None` (superadmins are global), commits, and prints a confirmation. Make it runnable as `python -m app.scripts.promote_superadmin <email>` from the `backend/` dir.
  - Search for any existing `scripts/` or `bin/` folder before adding new files; if a similar pattern exists (e.g. the demo seed referenced in recent commits), match it.

  **Implementation notes:**
  - Found existing `backend/scripts/seed_demo.py` (added in commit `3b7139b`, runnable as `python -m scripts.seed_demo` from `backend/`). Followed the explicit guidance in this task to match that pattern rather than creating a parallel `backend/app/scripts/` package — created `backend/scripts/promote_superadmin.py` instead, runnable as `cd backend && uv run python -m scripts.promote_superadmin <email>`. The next task's unit test invokes `main(email)` directly, so the import path matters: it's `from scripts.promote_superadmin import main`.
  - `main(email)` opens its own `SessionLocal()` (mirrors `seed_demo.main`), looks up the user via `UserRepository.get_by_email`, raises `SystemExit("User not found: …")` with a non-zero exit when missing, otherwise sets `role = UserRole.superadmin` and `organization_id = None`, commits + refreshes, and prints a confirmation line including the user's email and id. Re-promoting an already-superadmin user is a no-op idempotently (sets the same values).
  - The `if __name__ == "__main__":` guard validates `len(sys.argv) == 2` and emits a `Usage:` message via `SystemExit` otherwise. Verified `python -m scripts.promote_superadmin` (usage error), `python -m scripts.promote_superadmin nonexistent@example.com` (user-not-found error), and `from scripts.promote_superadmin import main` (clean import).

- [x] Add unit tests covering the new code:
  - `backend/tests/test_membership_model.py`: create user + org, create membership, assert relationships round-trip, assert unique constraint blocks duplicate (user, org) pairs
  - `backend/tests/test_membership_repository.py`: covers `list_for_user`, `list_for_organization`, `update_role`, `delete`, and `bulk_seed_from_legacy_user_org_id` (build legacy state, run, assert idempotent on second call)
  - `backend/tests/test_promote_superadmin.py`: invoke the CLI's `main(email)` against a seeded user and assert the role flips and `organization_id` is cleared
  - Re-use existing test fixtures (look in `backend/tests/conftest.py` for `db_session`, `user_factory`, `organization_factory` patterns) before inventing new ones

  **Implementation notes:**
  - `backend/tests/conftest.py` only rewrites the test DSN — there are no shared `db_session` / `user_factory` / `organization_factory` fixtures. Existing test files (e.g. `test_users_api.py`, `test_organizations_api.py`) inline a `setup_database` autouse fixture that creates/drops `Base.metadata`, plus local `_seed_user` / `_seed_org` helpers. Mirrored that exact pattern in all three new files for consistency.
  - `test_membership_model.py` (3 tests): asserts the `User.memberships` and `Organization.memberships` back-populates round-trip, exercises a single user holding memberships in two orgs, and confirms the `uq_user_org_membership` constraint raises `IntegrityError` on duplicate `(user_id, organization_id)` pairs.
  - `test_membership_repository.py` (8 tests): covers `list_for_user`, `list_for_organization`, `update_role` (success + missing-id), `delete` (success + missing-id), and the bulk seeder — including idempotence on a second call (returns 0, leaves row count unchanged) and skipping users with `organization_id IS NULL`.
  - `test_promote_superadmin.py` (3 tests): invokes `main(email)` directly (the test guidance from the previous task explicitly preserved this entry point) and asserts role/org-id mutation, idempotence on an already-promoted user, and the `SystemExit` path when the email isn't found. Captures stdout via `capsys` to confirm the confirmation line.
  - Full suite: `uv run pytest` → 161 passed (14 new + 147 pre-existing) in 5.70s, no regressions.

- [x] Wire openapi + lint + test gates:
  - Run `make openapi` so `backend/openapi.json` and `frontend/src/lib/schema.d.ts` pick up the new `MembershipRead` schema and the updated `UserRead.memberships` field
  - Run `make lint` and fix any issues
  - Run `make test` and fix any failures
  - Commit nothing — the user reviews and commits manually

  **Implementation notes:**
  - `make openapi` regenerated `backend/openapi.json` and `frontend/src/lib/schema.d.ts` cleanly. Diff: `MembershipRead` schema now exposed (id/user_id/organization_id/role/organization/created_at/updated_at) and `UserRead.memberships: MembershipRead[]` populated as expected (+22 lines in `schema.d.ts`).
  - `make lint` first run failed with two `ty` `invalid-argument-type` errors at `user_organization_membership_repository.py:96` — `user.id` and `user.organization_id` infer as `Column[Unknown] | Unknown` when read off a SQLAlchemy ORM instance and passed into `int`-typed `get(...)`. Codebase precedent for this exact case is a line-scoped `# type: ignore[invalid-argument-type]` (see `routers/communications.py:99`, `routers/documents.py:142`, `routers/capital_calls.py:98`). Applied the same suppression on line 96; second `make lint` run is fully green (ruff, ty, black, isort all clean).
  - `make test` → 161 passed in 5.96s. No regressions — the 14 new membership/superadmin tests from earlier tasks all pass alongside the 147 pre-existing tests.
  - Per task instructions, did not commit. Working tree changes left for user review: `backend/app/repositories/user_organization_membership_repository.py` (1-line type-ignore), `backend/openapi.json`, `frontend/src/lib/schema.d.ts`.
