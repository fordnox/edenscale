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

- [ ] Add the Pydantic schemas for memberships:
  - Create `backend/app/schemas/user_organization_membership.py` with `MembershipBase` / `MembershipCreate` / `MembershipUpdate` / `MembershipRead` following the style of `schemas/user.py`. `MembershipRead` should include nested `organization: OrganizationRead` and `role: UserRole` so the frontend can render the org switcher off a single endpoint
  - Update `schemas/user.py` `UserRead` to include an optional `memberships: list[MembershipRead] = []` field — but DO NOT remove `organization_id` yet (the migration to drop it lands later; keep both readable for now). Use a forward-ref / late import to avoid circular imports.

- [ ] Build the membership repository:
  - Create `backend/app/repositories/user_organization_membership_repository.py` mirroring the style of `repositories/user_repository.py`
  - Methods: `list_for_user(user_id)`, `list_for_organization(organization_id)`, `get(user_id, organization_id)`, `create(user_id, organization_id, role)`, `update_role(membership_id, role)`, `delete(membership_id)`, `bulk_seed_from_legacy_user_org_id()` — the bulk method idempotently creates memberships for every `User.organization_id is not None` that doesn't already have a row

- [ ] Author the alembic migration that adds the new schema:
  - Run `cd backend && uv run alembic revision -m "add user_organization_memberships and superadmin role" --autogenerate` (or hand-write if autogenerate misses the enum value addition — Postgres needs `ALTER TYPE user_role ADD VALUE 'superadmin'`)
  - The `upgrade()` must:
    1. Add `'superadmin'` to the existing `user_role` enum type (use `op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'superadmin'")` for Postgres; SQLite uses CHECK so just recreate the table — guard with `op.get_bind().dialect.name`)
    2. Create the `membership_role` enum type with all four values
    3. Create the `user_organization_memberships` table with FKs, unique constraint, and timestamp defaults
    4. Backfill: insert one membership row for every existing `users.organization_id is not null`, with `role` copied from `users.role` and `created_at = now()`
  - The `downgrade()` must drop the table and the enum type (do NOT downgrade the user_role enum value — that's a one-way door in PG; document this in a one-line comment)
  - Run `make upgrade` against the local SQLite DB and confirm it applies cleanly

- [ ] Add a CLI to manually promote a user to superadmin (since superadmin assignment is intentionally out-of-band):
  - Create `backend/app/scripts/__init__.py` and `backend/app/scripts/promote_superadmin.py` with a `main()` that takes `email` as a positional CLI arg, opens a session via `app.core.database.SessionLocal`, finds the user by email, sets `user.role = UserRole.superadmin` and `user.organization_id = None` (superadmins are global), commits, and prints a confirmation. Make it runnable as `python -m app.scripts.promote_superadmin <email>` from the `backend/` dir.
  - Search for any existing `scripts/` or `bin/` folder before adding new files; if a similar pattern exists (e.g. the demo seed referenced in recent commits), match it.

- [ ] Add unit tests covering the new code:
  - `backend/tests/test_membership_model.py`: create user + org, create membership, assert relationships round-trip, assert unique constraint blocks duplicate (user, org) pairs
  - `backend/tests/test_membership_repository.py`: covers `list_for_user`, `list_for_organization`, `update_role`, `delete`, and `bulk_seed_from_legacy_user_org_id` (build legacy state, run, assert idempotent on second call)
  - `backend/tests/test_promote_superadmin.py`: invoke the CLI's `main(email)` against a seeded user and assert the role flips and `organization_id` is cleared
  - Re-use existing test fixtures (look in `backend/tests/conftest.py` for `db_session`, `user_factory`, `organization_factory` patterns) before inventing new ones

- [ ] Wire openapi + lint + test gates:
  - Run `make openapi` so `backend/openapi.json` and `frontend/src/lib/schema.d.ts` pick up the new `MembershipRead` schema and the updated `UserRead.memberships` field
  - Run `make lint` and fix any issues
  - Run `make test` and fix any failures
  - Commit nothing — the user reviews and commits manually
