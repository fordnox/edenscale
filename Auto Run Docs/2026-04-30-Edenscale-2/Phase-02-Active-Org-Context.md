# Phase 02: Active Organization Context (Backend)

This phase introduces the `X-Organization-Id` request header and a new `get_active_membership` FastAPI dependency that resolves the membership row the caller is currently acting through. Every existing org-scoped router is then audited and migrated from `current_user.organization_id` (the legacy single-org column) to `active_membership.organization_id` and `active_membership.role`. Superadmins can act on any org by passing the header; admins/fund_managers/lps can only act on orgs where they have a membership.

## Tasks

- [x] Re-read the supporting files and inventory every call site that needs an audit:
  - `backend/app/core/rbac.py`, `backend/app/main.py`
  - Search for every reference to `current_user.organization_id`, `user.organization_id`, and `users.organization_id` under `backend/app/routers/` and `backend/app/repositories/` and write the file:line list to `Auto Run Docs/2026-04-30-Edenscale-2/Working/active-org-audit.md` (markdown bullet list) so nothing is missed during the migration

  **Implementation notes:**
  - Re-read `backend/app/core/rbac.py` (current contents: `get_current_user_record` and `require_roles`; no `organization_id` reads — Phase 02 will add `get_active_membership` here as a sibling dep) and `backend/app/main.py` (15 routers mounted under `/dashboard`, `/users`, `/organizations`, `/fund-groups`, `/funds`, `/investors`, `/commitments`, `/capital-calls`, `/distributions`, `/documents`, `/communications`, `/tasks`, `/notifications`, `/audit-logs` — each currently gated only by `Depends(get_current_user)` at the include-router level).
  - Searched routers + repositories for `current_user.organization_id`, `user.organization_id`, `users.organization_id`. Wrote the full file:line inventory to `Auto Run Docs/2026-04-30-Edenscale-2/Working/active-org-audit.md`: **32 router hits across 14 files**, **29 repository hits across 9 files**.
  - Routers needing migration: `funds`, `fund_groups`, `fund_team_members`, `investors`, `investor_contacts`, `commitments`, `capital_calls`, `distributions`, `documents`, `communications`, `tasks`, `dashboard`, `users`. Routers with no direct hits but flagged for manual review during migration: `notifications`, `audit_logs` (their org-scoping may live downstream in repositories).
  - Repositories needing scope-source change: `fund_repository`, `capital_call_repository`, `investor_repository`, `commitment_repository`, `distribution_repository`, `document_repository`, `communication_repository`, `task_repository`. Each currently accepts a `User` and reads `user.organization_id`; cleanest migration is to change these signatures to take `organization_id` directly so the active-membership decision stays in the router/dep layer.
  - Out-of-scope hits documented in the audit doc: `user_organization_membership_repository.py` lines 84/96/102 (seeder is supposed to read the legacy column), `core/audit.py:147` (audit log writer — flagged for a follow-up decision: switch to active-membership org or leave on legacy column for audit-row provenance; not explicitly in Phase 02 task list).
  - `users.organization_id` (the SQL column name) appears only inside the membership repo's docstring — no production callsite reads the raw column name.

- [ ] Build the `get_active_membership` dependency in `backend/app/core/rbac.py`:
  - Add `def get_active_membership(...)` that depends on `get_current_user_record` and the `X-Organization-Id` header (`Header(alias="X-Organization-Id")`, optional)
  - Resolution rules:
    - If header missing AND user has exactly one membership, use it
    - If header missing AND user is superadmin, return `None` (let downstream choose) OR raise 400 with `"X-Organization-Id required"` — pick "raise" for org-scoped routes; superadmin-only routes get a separate dep that allows None
    - If header present, look up the membership for `(user_id, organization_id)`; if found, return it; if user is `superadmin` and no membership exists, synthesize a transient `Membership`-like object with `role=superadmin` and `organization_id=<header>` (do NOT persist) so superadmins can act on any org
    - If header references an org the user has no membership in and they are NOT superadmin, raise 403 `"Not a member of this organization"`
  - Add `require_membership_roles(*allowed: UserRole)` factory analogous to `require_roles` but operating on the active membership's `role` (so a user who is `lp` globally but `admin` of Org B is treated as admin within Org B)
  - Keep the legacy `require_roles` working for now so superadmin-only / global-scoped routes (like superadmin org management) can still gate on `User.role`

- [ ] Migrate every org-scoped router off `current_user.organization_id`:
  - For each file from the audit (`funds`, `fund_groups`, `fund_team_members`, `investors`, `investor_contacts`, `commitments`, `capital_calls`, `distributions`, `documents`, `communications`, `tasks`, `notifications`, `dashboard`, `audit_logs`, `users`):
    - Replace the `current_user: User = Depends(require_roles(...))` pattern with `membership: UserOrganizationMembership = Depends(require_membership_roles(...))` where appropriate
    - Use `membership.organization_id` for query scoping
    - Use `membership.role` for in-org authorization checks
    - Where a route legitimately operates outside an org (e.g. `/users/me`, `/users/me` patches, list-my-memberships), keep it on `get_current_user_record`
  - The `/users` invite endpoint and `/users/{id}/role` endpoint will move to membership-based management in Phase 04 — for now, leave them but make them noop-safely on superadmins (return 400 with a clear message saying invitations are the new path)

- [ ] Add a `/users/me/memberships` route returning `list[MembershipRead]`:
  - Create or extend `backend/app/routers/users.py` with `GET /me/memberships`
  - The frontend will use this to populate the org switcher in Phase 05

- [ ] Add tests for the new dependency and the migrated routers:
  - `backend/tests/test_active_membership_dep.py`: header missing + single membership = resolves; header present + match = resolves; header present + no match + non-superadmin = 403; header present + superadmin = synthesized membership; header missing + superadmin = 400
  - For one already-tested router (e.g. `funds`), update the existing test to pass `X-Organization-Id` and assert cross-org leakage is blocked
  - `backend/tests/test_users_memberships_route.py`: returns memberships including org payload and per-org role

- [ ] Run the gate trio and fix any breakage:
  - `make openapi` (the new header param + memberships route change the schema)
  - `make lint`
  - `make test`
