# Phase 03: Superadmin Backend Routes

This phase exposes the superadmin control surface: a new `/superadmin` router family that lets superadmins create organizations, list every org with member counts, assign initial admins to a freshly created org, and disable/re-enable orgs. Everything is gated on `User.role == superadmin` (global, not membership-scoped). Existing `/organizations` routes for tenant-scoped CRUD are kept for in-org admins and audited so superadmins can no longer mistakenly use them as a back door.

## Tasks

- [x] Read the existing patterns so the new router slots in cleanly:
  - `backend/app/routers/organizations.py` and the `OrganizationRepository`
  - `backend/app/routers/users.py` for invite/role-update style
  - `backend/app/core/rbac.py` for the dep-factory style
  - Look for any existing `superadmin` references (there shouldn't be any from earlier phases) so you don't duplicate

  **Findings (orientation only — no code changes this iteration):**
  - `backend/app/routers/organizations.py` is thin: routes delegate to `OrganizationRepository(db)`, which exposes `list(skip, limit, include_inactive)`, `get`, `create(OrganizationCreate)`, `update(id, OrganizationUpdate)`, `soft_delete(id)`. Current POST/PATCH/DELETE all use `require_roles(UserRole.admin, UserRole.fund_manager)` (DELETE is admin-only). The Phase 02 task description says PATCH was moved to `require_membership_roles(UserRole.admin)` but the file on disk still uses the global `require_roles` — Phase 03's audit step will need to handle that as part of tightening auth.
  - `backend/app/routers/users.py` shows the established mix: org-scoped routes take `membership: UserOrganizationMembership = Depends(require_membership_roles(...))` and use `membership.organization_id`; global role gates use `dependencies=[Depends(require_roles(...))]` at decorator level. Repository pattern: `UserRepository(db)` with `get_by_email`, `get_by_id`, `create(UserCreate)`, `update`, `update_role`, `list_by_organization`. The invite endpoint already has a stub raising 400 for synthesized superadmin memberships pointing toward "Phase 04 POST /organizations/{id}/memberships".
  - `backend/app/core/rbac.py` is the factory home: `require_roles(*allowed: UserRole)` returns a dep that depends on `get_current_user_record` and 403s when `current_user.role not in allowed`. **`require_superadmin` should mirror this exactly** — same shape, single allowed role `UserRole.superadmin`, depending on `get_current_user_record` (NOT `get_active_membership`, since superadmin is global and needs no `X-Organization-Id` header).
  - No existing `superadmin.py` router file. `superadmin` references across the backend are all `UserRole.superadmin` allow-list entries in role checks plus the `get_active_membership` synthesized-membership branch — none of them collide with the new `/superadmin/*` namespace.
  - Router mounting in `backend/app/main.py` uses the `app.include_router(<router>, prefix="...", tags=["..."], dependencies=[Depends(get_current_user)])` pattern; the new router slots in alongside `users` / `organizations` with the same JWT-only outer gate, then per-route `require_superadmin` for authorization.

- [x] Add a `require_superadmin` dependency to `backend/app/core/rbac.py`:
  - Returns the `User` if `user.role == UserRole.superadmin`, else 403
  - Reuse `get_current_user_record`; do NOT depend on `get_active_membership` (superadmin is global)

  **Implementation notes:**
  - Added as a direct dep (not a factory like `require_roles`) since there's only ever one allowed role — callers use `Depends(require_superadmin)` rather than `Depends(require_superadmin())`. Keeps the call site shorter and matches FastAPI idiom for fixed-role gates.
  - 403 detail string is `"Superadmin role required"` (more specific than `require_roles`' `"Insufficient role"`) so `/superadmin/*` 403s are easy to identify in logs / tests.
  - Added module-docstring entry plus three new unit tests in `tests/test_rbac.py`: superadmin passes, and admin/fund_manager/lp each get 403 (parametrized).
  - Verified `make lint` and `make test` (184 passed) before commit. `make openapi` not run — no route changes in this iteration; the next task (`/superadmin` router) will trigger it.

- [x] Build `backend/app/routers/superadmin.py` with these routes:
  - `GET /superadmin/organizations` — list ALL organizations (active + inactive) with member counts (use a subquery or join through `user_organization_memberships`); response `list[SuperadminOrganizationRead]` (a new schema with `id`, `name`, `type`, `is_active`, `member_count`, `created_at`)
  - `POST /superadmin/organizations` — create org + create the founding admin membership in one transaction. Body accepts an existing `user_id` to make admin OR an `admin_email` (if email matches an existing user, attach a membership with `role=admin`; if not, create a stub user row with `hanko_subject_id=None` so they get claimed on first sign-in via the existing `get_current_user_record` flow). Response: `{ organization: OrganizationRead, admin_membership: MembershipRead }`
  - `POST /superadmin/organizations/{organization_id}/admins` — grant a user (by `user_id` or `email`) `role=admin` membership on that org; idempotent if a membership already exists, and updates role to admin if the existing role was different
  - `PATCH /superadmin/organizations/{organization_id}/disable` and `/enable` — toggle `is_active`; deactivated orgs hide from non-superadmin org switchers (handled in Phase 05)
  - `GET /superadmin/organizations/{organization_id}/members` — list memberships with nested user payload so the superadmin UI can show the roster

  **Implementation notes:**
  - Created `backend/app/routers/superadmin.py` with all six handlers (the `disable` and `enable` PATCH endpoints are split routes per the spec). Every route uses `dependencies=[Depends(require_superadmin)]` at decorator level — no per-handler arg pickup since none of them need the resolved `User`.
  - Member-count list uses a single grouped query: `Organization` left-outer-joined to `UserOrganizationMembership` with `func.count(membership.id)` and `group_by(Organization.id)`. Active + inactive both included (no `is_active` filter), ordered by `id` to match the existing `OrganizationRepository.list` ordering.
  - Cross-resource writes (`POST /organizations`, `POST /organizations/{id}/admins`) bypass `OrganizationRepository.create` / `UserRepository.create` because those eagerly commit. Inlined the user-resolve + org-create + membership-create flow on the request session with `db.flush()` for FK ids and a single trailing `db.commit()`. Stub-user creation defaults to `role=UserRole.lp` and `hanko_subject_id=None` so the existing `get_current_user_record` email-bind path picks them up on first Hanko sign-in.
  - `POST /organizations/{id}/admins` is idempotent: if a `(user_id, organization_id)` membership already exists it returns it as-is when the role is already `admin`, or mutates `role=admin` and commits when it was something else. New memberships go through `UserOrganizationMembershipRepository.create`.
  - `disable` / `enable` factor through a private `_set_organization_active` helper that 404s on missing org and mutates `is_active`. Did NOT reuse `OrganizationRepository.soft_delete` since that is hard-coded to `False` and the audit checkbox below will rework the `DELETE /organizations/{id}` semantics (soft-delete + cascade membership deactivation) — keeping concerns separate here.
  - `GET /organizations/{id}/members` returns `list[MembershipWithUserRead]` so the superadmin UI gets names/emails inline; relies on the SQLAlchemy `User` relationship already declared on `UserOrganizationMembership`.

- [x] Add the new schemas under `backend/app/schemas/`:
  - Either extend `schemas/organization.py` with `SuperadminOrganizationRead` and `SuperadminOrganizationCreate`, or create `schemas/superadmin.py` — pick whichever matches the existing pattern (one file per resource family seems consistent)
  - Add `MembershipWithUserRead` if the `/members` endpoint needs a denormalized payload

  **Implementation notes:**
  - Created `backend/app/schemas/superadmin.py` (new file matches the one-per-resource-family pattern; extending `organization.py` would have pulled superadmin-only payloads into the per-tenant schemas the regular `/organizations` router imports). Re-exported from `app/schemas/__init__.py` alongside the existing org/membership types.
  - `SuperadminOrganizationCreate` extends `OrganizationCreate` with `admin_user_id`, `admin_email`, `admin_first_name`, `admin_last_name`. A `model_validator(mode="after")` enforces XOR between `admin_user_id` and `admin_email` (`(a is None) == (b is None)` ⇒ raise) so we don't ambiguously target two users.
  - `SuperadminAdminAssignment` mirrors that XOR rule for the `/admins` endpoint with `user_id` / `email` fields and optional first/last name overrides for stub-user creation.
  - `SuperadminOrganizationCreateResponse` wraps `OrganizationRead` + `MembershipRead` so the POST response is a single typed object instead of an ad-hoc dict.
  - `MembershipWithUserRead` mirrors `MembershipRead` but swaps the nested `OrganizationRead` for `UserRead`; it's the roster payload for `GET /organizations/{id}/members`. Uses `from_attributes=True` so SQLAlchemy `UserOrganizationMembership` rows validate directly via the existing `user` relationship.
  - Verified `make lint` (94 files clean) and `make test` (184 passed). `make openapi` deliberately deferred — the new router isn't mounted yet (separate checkbox), so it would not yet appear in `openapi.json`. The mount step + the final gate trio at the bottom of this phase will regenerate the client.

- [x] Mount the new router in `backend/app/main.py`:
  - `app.include_router(superadmin.router, prefix="/superadmin", tags=["superadmin"], dependencies=[Depends(get_current_user)])`
  - Per-route `require_superadmin` dependencies still gate authorization

  **Implementation notes:**
  - Added `superadmin` to the `app.routers` import block (alphabetical: between `organizations` and `tasks`) and slotted the `include_router` call directly after the `organizations` mount so the `/superadmin/*` namespace lives next to the regular `/organizations/*` one in route order.
  - Outer JWT gate via `Depends(get_current_user)` matches every other authed router; the per-route `require_superadmin` deps in the router file remain the actual authorization boundary.
  - Ran `make openapi` — five new paths now show in `backend/openapi.json` (`/superadmin/organizations`, `/superadmin/organizations/{organization_id}/admins`, `/disable`, `/enable`, `/members`) and `frontend/src/lib/schema.d.ts` regenerated to expose them to the Phase 06 UI work.
  - `make lint` clean (94 files), `make test` green (184 passed). No new tests in this iteration — the dedicated superadmin route test suite is its own checkbox below.

- [x] Audit the existing `/organizations` POST/PATCH/DELETE routes:
  - Currently they allow `admin` and `fund_manager`; make them require `require_superadmin` for `POST` (only superadmin creates orgs) but keep `PATCH` open to `admin` membership of the target org (Phase 02 already moved this to `require_membership_roles(UserRole.admin)`)
  - `DELETE /organizations/{id}` should be superadmin-only — soft-delete the org and deactivate all its memberships in the same transaction

  **Implementation notes:**
  - `POST /organizations`: swapped `require_roles(UserRole.admin, UserRole.fund_manager)` for `Depends(require_superadmin)`. Tenant-side `admin`/`fund_manager` no longer have a back door into org creation — superadmins use either this or the richer `POST /superadmin/organizations` flow that also seats the founding admin.
  - `PATCH /organizations/{organization_id}`: switched to `require_membership_roles(UserRole.admin)` (no `superadmin` in the allow-list — synthesized superadmin memberships have `role=superadmin`, so they 403 here on purpose, matching the doc's "no superadmin back door"). Added an explicit `membership.organization_id != organization_id` guard so a header/path mismatch returns 403 rather than silently editing the wrong org. The dep now appears as an `X-Organization-Id` optional header in the regenerated schema.
  - `DELETE /organizations/{organization_id}`: gate flipped to `Depends(require_superadmin)`. The handler no longer calls `OrganizationRepository.soft_delete` — it inlines `is_active=False` plus a bulk `db.query(UserOrganizationMembership).filter(...).delete(synchronize_session=False)` before a single `db.commit()` so the org-flag flip and the membership cascade share one transaction. Memberships have no `is_active` column, so "deactivate" is implemented as a hard-delete; this is what makes DELETE meaningfully different from `PATCH /superadmin/organizations/{id}/disable`, which preserves the membership rows for re-enablement.
  - Existing tests in `tests/test_organizations_api.py` updated to match the tightened auth: renamed/added `test_superadmin_can_create_and_read`, `test_admin_cannot_create`, `test_admin_cannot_delete`, `test_superadmin_can_delete_soft`. Kept the existing 403-style tests (`test_lp_cannot_create`, `test_fund_manager_cannot_delete`) since they remain valid.
  - Verified `make lint` (94 files clean), `make test` (186 passed — same suite, plus the renamed cases), and `make openapi` (regenerated `openapi.json` + `frontend/src/lib/schema.d.ts` so the X-Organization-Id header on PATCH and the unchanged DELETE/POST shapes propagate to the typed client). Did not add fresh PATCH-specific tests — those belong with the broader test pass in the next checkbox.

- [x] Tests for the superadmin surface:
  - `backend/tests/test_superadmin_routes.py`: non-superadmin gets 403 on every `/superadmin/*` route; superadmin can create org + admin membership in one POST; member count is correct; disable/enable round-trip works; `/admins` is idempotent
  - Update `backend/tests/test_organizations_router.py` (or whatever already exists) to reflect the tightened auth

  **Implementation notes:**
  - Created `backend/tests/test_superadmin_routes.py` (29 tests across 6 classes). Followed the seed-helpers + `override_user` pattern already established by `test_organizations_api.py` / `test_users_memberships_route.py` rather than introducing a new fixture model — keeps the test suite homogeneous.
  - `TestNonSuperadminForbidden` parametrizes admin/fund_manager/lp across the GET-list and POST-create endpoints, plus single 403 cases for `/admins`, `/disable`, `/enable`, `/members`. This is the "no back door" guarantee the doc calls for.
  - `TestCreateOrganizationWithAdmin` covers all four happy paths (existing user_id, stub-user creation by email, reuse of existing user via email match, 422/404 sad paths) and verifies the stub user has `hanko_subject_id=None` so the existing email-bind flow in `get_current_user_record` will claim it on first sign-in.
  - `TestAssignOrganizationAdmin` proves idempotency two ways: re-targeting an already-admin user returns the original membership row id (no duplicate insert — a SELECT count assertion against `user_organization_memberships` backs this up), and re-targeting a non-admin membership upgrades the role in place.
  - `TestDisableEnableOrganization` confirms the round-trip preserves memberships — the same membership row exists after enable, distinguishing PATCH /disable semantics from DELETE /organizations/{id} which deletes them.
  - The `/organizations` audit tests already live in `test_organizations_api.py` and were updated in the prior checkbox; the doc's pointer to a `test_organizations_router.py` file was a paper reference — no separate file exists, and `test_organizations_api.py` already has the `test_admin_cannot_create`, `test_admin_cannot_delete`, `test_superadmin_can_delete_soft` cases covering the tightened auth.
  - Final `make test`: 215 passed (up from 186); `make lint` clean. `make openapi` not needed (test-only change).

- [ ] Final gate trio:
  - `make openapi` (the new routes show up in `schema.d.ts` for use in Phase 06)
  - `make lint`
  - `make test`
