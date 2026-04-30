# Phase 03: Superadmin Backend Routes

This phase exposes the superadmin control surface: a new `/superadmin` router family that lets superadmins create organizations, list every org with member counts, assign initial admins to a freshly created org, and disable/re-enable orgs. Everything is gated on `User.role == superadmin` (global, not membership-scoped). Existing `/organizations` routes for tenant-scoped CRUD are kept for in-org admins and audited so superadmins can no longer mistakenly use them as a back door.

## Tasks

- [ ] Read the existing patterns so the new router slots in cleanly:
  - `backend/app/routers/organizations.py` and the `OrganizationRepository`
  - `backend/app/routers/users.py` for invite/role-update style
  - `backend/app/core/rbac.py` for the dep-factory style
  - Look for any existing `superadmin` references (there shouldn't be any from earlier phases) so you don't duplicate

- [ ] Add a `require_superadmin` dependency to `backend/app/core/rbac.py`:
  - Returns the `User` if `user.role == UserRole.superadmin`, else 403
  - Reuse `get_current_user_record`; do NOT depend on `get_active_membership` (superadmin is global)

- [ ] Build `backend/app/routers/superadmin.py` with these routes:
  - `GET /superadmin/organizations` — list ALL organizations (active + inactive) with member counts (use a subquery or join through `user_organization_memberships`); response `list[SuperadminOrganizationRead]` (a new schema with `id`, `name`, `type`, `is_active`, `member_count`, `created_at`)
  - `POST /superadmin/organizations` — create org + create the founding admin membership in one transaction. Body accepts an existing `user_id` to make admin OR an `admin_email` (if email matches an existing user, attach a membership with `role=admin`; if not, create a stub user row with `hanko_subject_id=None` so they get claimed on first sign-in via the existing `get_current_user_record` flow). Response: `{ organization: OrganizationRead, admin_membership: MembershipRead }`
  - `POST /superadmin/organizations/{organization_id}/admins` — grant a user (by `user_id` or `email`) `role=admin` membership on that org; idempotent if a membership already exists, and updates role to admin if the existing role was different
  - `PATCH /superadmin/organizations/{organization_id}/disable` and `/enable` — toggle `is_active`; deactivated orgs hide from non-superadmin org switchers (handled in Phase 05)
  - `GET /superadmin/organizations/{organization_id}/members` — list memberships with nested user payload so the superadmin UI can show the roster

- [ ] Add the new schemas under `backend/app/schemas/`:
  - Either extend `schemas/organization.py` with `SuperadminOrganizationRead` and `SuperadminOrganizationCreate`, or create `schemas/superadmin.py` — pick whichever matches the existing pattern (one file per resource family seems consistent)
  - Add `MembershipWithUserRead` if the `/members` endpoint needs a denormalized payload

- [ ] Mount the new router in `backend/app/main.py`:
  - `app.include_router(superadmin.router, prefix="/superadmin", tags=["superadmin"], dependencies=[Depends(get_current_user)])`
  - Per-route `require_superadmin` dependencies still gate authorization

- [ ] Audit the existing `/organizations` POST/PATCH/DELETE routes:
  - Currently they allow `admin` and `fund_manager`; make them require `require_superadmin` for `POST` (only superadmin creates orgs) but keep `PATCH` open to `admin` membership of the target org (Phase 02 already moved this to `require_membership_roles(UserRole.admin)`)
  - `DELETE /organizations/{id}` should be superadmin-only — soft-delete the org and deactivate all its memberships in the same transaction

- [ ] Tests for the superadmin surface:
  - `backend/tests/test_superadmin_routes.py`: non-superadmin gets 403 on every `/superadmin/*` route; superadmin can create org + admin membership in one POST; member count is correct; disable/enable round-trip works; `/admins` is idempotent
  - Update `backend/tests/test_organizations_router.py` (or whatever already exists) to reflect the tightened auth

- [ ] Final gate trio:
  - `make openapi` (the new routes show up in `schema.d.ts` for use in Phase 06)
  - `make lint`
  - `make test`
