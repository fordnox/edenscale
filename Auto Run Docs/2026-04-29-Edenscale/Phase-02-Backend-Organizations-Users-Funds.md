# Phase 02: Backend — Organizations, Users, Funds

This phase delivers the first slice of real CRUD for the platform: organizations (firms), users (with the Hanko-backed `role` field driving RBAC), fund groups, funds, and fund team members. By the end of this phase, an authenticated fund_manager can create their organization, invite team members, create fund groups, and create/update/list/archive funds via the API. Role enforcement uses a small dependency that reads the JWT subject, looks up the local `User` row, and rejects requests where the role does not match the route's allow-list.

## Tasks

- [ ] Re-read existing patterns before adding new code:
  - Read `backend/app/routers/users.py`, `backend/app/repositories/user_repository.py`, `backend/app/schemas/user.py`, `backend/app/core/auth.py`, `backend/app/main.py` to mirror the existing router → repository → model → schema layering
  - Read every model file created in Phase 01 to confirm column names and relationships before referencing them in repositories

- [ ] Add an RBAC dependency layer alongside the existing JWT check:
  - Create `backend/app/core/rbac.py` exposing `get_current_user_record(db: Session = Depends(get_db), payload: dict = Depends(get_current_user)) -> User` which finds-or-creates the local `User` row keyed by `hanko_subject_id = payload["sub"]`. On first sight, create the row with `role=UserRole.lp` and copy email/first_name/last_name from the JWT claims if present; otherwise leave them blank and let the user complete their profile later
  - Add `require_roles(*allowed: UserRole)` factory that returns a FastAPI dependency raising `HTTPException(403)` when `current_user.role not in allowed`
  - Add unit tests in `backend/tests/test_rbac.py` covering: unknown subject auto-provisioning, role-allowed pass-through, role-denied 403

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
