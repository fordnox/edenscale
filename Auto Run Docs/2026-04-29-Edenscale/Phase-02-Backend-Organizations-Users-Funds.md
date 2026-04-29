# Phase 02: Backend — Organizations, Users, Funds

This phase delivers the first slice of real CRUD for the platform: organizations (firms), users (with the Hanko-backed `role` field driving RBAC), fund groups, funds, and fund team members. By the end of this phase, an authenticated fund_manager can create their organization, invite team members, create fund groups, and create/update/list/archive funds via the API. Role enforcement uses a small dependency that reads the JWT subject, looks up the local `User` row, and rejects requests where the role does not match the route's allow-list.

## Tasks

- [x] Re-read existing patterns before adding new code:
  - Read `backend/app/routers/users.py`, `backend/app/repositories/user_repository.py`, `backend/app/schemas/user.py`, `backend/app/core/auth.py`, `backend/app/main.py` to mirror the existing router → repository → model → schema layering
  - Read every model file created in Phase 01 to confirm column names and relationships before referencing them in repositories
  - **Notes for Phase 02 implementers:**
    - Existing layering: `routers/` instantiate a repository per request, repos hold the `Session`, schemas live in `schemas/`. Routers do not contain business logic. `main.py` mounts router groups with `Depends(get_current_user)` declared on `include_router` (not on individual routes).
    - `User` columns to honour (`backend/app/models/user.py`): `id` (int autoincrement), `organization_id` (nullable FK), `role` (UserRole enum, NOT NULL), `first_name`/`last_name` (NOT NULL `String(100)`), `email` (unique, NOT NULL), `phone`, `title`, `password_hash` (NOT NULL with `default=""`), `is_active` (NOT NULL default true), `last_login_at`, `hanko_subject_id` (nullable, unique, indexed), `created_at`/`updated_at`.
    - The existing `UserCreate`/`UserResponse` in `backend/app/schemas/user.py` are stale placeholders (`id: str`, `name: str`, `picture: str`) — they don't match the new `User` model. Phase 02 must replace them, not extend them, when adding `UserRead`/`UserCreate`/`UserUpdate`/`UserRoleUpdate`.
    - The existing `UserRepository` exposes `get_all/get_by_id/create/update/delete` only and `create()` uses `User(**data.model_dump())` — that will fail under the real schema (missing `role`, `first_name`, `last_name`). Need to rewrite, not just add helpers.
    - The placeholder routes in `backend/app/routers/users.py` use `PUT /{user_id}` and `DELETE /{user_id}` and rely on stale schemas — they'll be removed in favour of the new endpoints.
    - `Organization` (`backend/app/models/organization.py`): `id`, `type` (OrganizationType enum, NOT NULL), `name` (NOT NULL), `legal_name`, `tax_id`, `website`, `description`, `is_active` (default true), `created_at`/`updated_at`. Soft-delete = `is_active=False`.
    - `Fund` (`backend/app/models/fund.py`): `organization_id` NOT NULL, `fund_group_id` nullable, `name` NOT NULL, `legal_name`, `vintage_year`, `strategy`, `currency_code` NOT NULL default `"USD"`, `target_size`, `hard_cap`, `current_size` (Numeric default 0 — but Phase 02 mandates computing it as `SUM(commitments.committed_amount)` at read time), `status` (FundStatus enum default `draft`), `inception_date`, `close_date`, `description`. `archive` = set `status=FundStatus.archived`.
    - `FundGroup` (`backend/app/models/fund_group.py`): `organization_id` NOT NULL, `name` NOT NULL, `description`, `created_by_user_id` (nullable FK to users).
    - `FundTeamMember` (`backend/app/models/fund_team_member.py`): composite uniqueness already enforced via `UniqueConstraint("fund_id","user_id")`. Fields: `fund_id`, `user_id`, `title`, `permissions` (Text — likely JSON-as-text).
    - LP-visibility joins for `list_for_user`: `User -> InvestorContact (user_id)` -> `Investor` -> `Commitment (investor_id)` -> `Fund (fund_id)`. `InvestorContact.user_id` is nullable so we filter on the non-null match.
    - `commitments.committed_amount` is `Numeric(18,2)` NOT NULL — safe to `SUM(...)` and `COALESCE` to 0.
    - Auth contract: `get_current_user` (`backend/app/core/auth.py`) returns the decoded JWT payload as a `dict`. Phase 02's `get_current_user_record` must accept this dict (not a typed model) and key on `payload["sub"]` for `hanko_subject_id`. JWT claim names for email/given_name/family_name should be probed defensively (`payload.get("email")`, `payload.get("given_name")`, `payload.get("family_name")`) and fall back to empty strings since first_name/last_name are NOT NULL.
    - All routers under Phase 02 mount via `app.include_router(..., dependencies=[Depends(get_current_user)])` to match the existing pattern; per-route role enforcement uses `Depends(require_roles(...))` from the new `app/core/rbac.py`.

- [x] Add an RBAC dependency layer alongside the existing JWT check:
  - Create `backend/app/core/rbac.py` exposing `get_current_user_record(db: Session = Depends(get_db), payload: dict = Depends(get_current_user)) -> User` which finds-or-creates the local `User` row keyed by `hanko_subject_id = payload["sub"]`. On first sight, create the row with `role=UserRole.lp` and copy email/first_name/last_name from the JWT claims if present; otherwise leave them blank and let the user complete their profile later
  - Add `require_roles(*allowed: UserRole)` factory that returns a FastAPI dependency raising `HTTPException(403)` when `current_user.role not in allowed`
  - Add unit tests in `backend/tests/test_rbac.py` covering: unknown subject auto-provisioning, role-allowed pass-through, role-denied 403
  - **Notes:** Implemented `get_current_user_record` to raise 401 (not autoprovision) when the JWT lacks a `sub` claim — without `hanko_subject_id` the unique constraint would force a NULL collision later. New users default to `role=UserRole.lp` per spec; claims pulled defensively via `payload.get(...)`. Six unit tests in `backend/tests/test_rbac.py` cover provisioning (with and without claims), idempotent return for an existing user (claims do NOT overwrite stored values), missing-subject 401, and role allow/deny on the `require_roles` factory.

- [ ] Implement the Organizations slice end-to-end:
  - `backend/app/schemas/organization.py` — `OrganizationCreate`, `OrganizationUpdate`, `OrganizationRead` with all dbml fields
  - `backend/app/repositories/organization_repository.py` — `list`, `get`, `create`, `update`, `soft_delete` (set `is_active=False`)
  - `backend/app/routers/organizations.py` — `GET /organizations`, `GET /organizations/{id}`, `POST /organizations` (admin or fund_manager only), `PATCH /organizations/{id}`, `DELETE /organizations/{id}` (admin only)
  - Mount the router in `backend/app/main.py` under `/organizations` with `Depends(get_current_user)` on `include_router`

- [ ] Implement the Users slice (extending the existing module):
  - Extend `backend/app/schemas/user.py` with `UserRead`, `UserCreate`, `UserUpdate`, `UserRoleUpdate` covering all dbml columns plus `hanko_subject_id`
  - Extend `backend/app/repositories/user_repository.py` with `list_by_organization`, `get_by_email`, `get_by_hanko_subject`, `create`, `update`, `update_role`, `set_active`, `record_last_login`
  - Extend `backend/app/routers/users.py` to expose `GET /users/me` (returns the local record from `get_current_user_record`), `PATCH /users/me` (self-edit name/phone/title), `GET /users` (admin or fund_manager — list within own organization), `POST /users` (admin or fund_manager — invite), `PATCH /users/{id}` (admin or fund_manager scoped to org), `PATCH /users/{id}/role` (admin only). Remove the placeholder routes in favor of these
  - Add `backend/tests/test_users_api.py` covering `/users/me` happy path and admin-only role change rejection

- [ ] Implement Fund Groups:
  - Schemas, repository, router for `GET /fund-groups`, `GET /fund-groups/{id}`, `POST /fund-groups`, `PATCH /fund-groups/{id}`, `DELETE /fund-groups/{id}`
  - Restrict list/create to `fund_manager` and `admin`; LPs may only `GET /fund-groups/{id}` for groups whose funds they have commitments in (defer the LP visibility filter to a later phase if it adds friction — leave a `# TODO: scope to LP commitments` and gate to fund_manager+admin for now)
  - Mount under `/fund-groups`

- [ ] Implement Funds:
  - `backend/app/schemas/fund.py` — `FundCreate`, `FundUpdate`, `FundRead`, `FundListItem` with all dbml fields including `current_size` (computed at read time as `SUM(commitments.committed_amount)` so it's always accurate; do not require clients to set it)
  - `backend/app/repositories/fund_repository.py` — `list_for_user(user)` returns funds the caller is allowed to see (admin: all; fund_manager: same organization; lp: funds they hold a commitment in via the `commitments` table joined on the user's investor_contacts), `get`, `create`, `update`, `archive` (sets status=archived)
  - `backend/app/routers/funds.py` — `GET /funds`, `GET /funds/{id}`, `POST /funds` (fund_manager+admin), `PATCH /funds/{id}` (fund_manager+admin), `POST /funds/{id}/archive` (fund_manager+admin)
  - Mount under `/funds`

- [ ] Implement Fund Team Members:
  - Schemas/repository/router for adding and removing team members with composite uniqueness `(fund_id, user_id)`
  - Endpoints: `GET /funds/{fund_id}/team`, `POST /funds/{fund_id}/team`, `PATCH /funds/{fund_id}/team/{member_id}`, `DELETE /funds/{fund_id}/team/{member_id}`
  - Mount the router under `/funds` so it nests cleanly

- [ ] Add focused integration tests:
  - `backend/tests/test_organizations_api.py` — admin can create + read; fund_manager can read but not delete
  - `backend/tests/test_funds_api.py` — fund_manager creates a fund in own org; LP cannot create; LP can list only funds they have commitments in; archive flips status
  - Use the existing test fixtures pattern from `backend/tests/`; add a fixture that mints a JWT-equivalent header and seeds matching local User rows directly (bypassing real Hanko)

- [ ] Sync the OpenAPI client and run quality gates:
  - Run `make openapi` to regenerate `backend/openapi.json` and `frontend/src/lib/schema.d.ts`
  - Run `make test` and `make lint` and resolve any findings
  - Confirm `frontend/src/lib/schema.d.ts` now lists every new path so Phase 06+ can consume them
