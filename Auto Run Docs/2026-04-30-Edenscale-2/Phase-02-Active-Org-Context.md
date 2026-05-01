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

- [x] Build the `get_active_membership` dependency in `backend/app/core/rbac.py`:
  - Add `def get_active_membership(...)` that depends on `get_current_user_record` and the `X-Organization-Id` header (`Header(alias="X-Organization-Id")`, optional)
  - Resolution rules:
    - If header missing AND user has exactly one membership, use it
    - If header missing AND user is superadmin, return `None` (let downstream choose) OR raise 400 with `"X-Organization-Id required"` — pick "raise" for org-scoped routes; superadmin-only routes get a separate dep that allows None
    - If header present, look up the membership for `(user_id, organization_id)`; if found, return it; if user is `superadmin` and no membership exists, synthesize a transient `Membership`-like object with `role=superadmin` and `organization_id=<header>` (do NOT persist) so superadmins can act on any org
    - If header references an org the user has no membership in and they are NOT superadmin, raise 403 `"Not a member of this organization"`
  - Add `require_membership_roles(*allowed: UserRole)` factory analogous to `require_roles` but operating on the active membership's `role` (so a user who is `lp` globally but `admin` of Org B is treated as admin within Org B)
  - Keep the legacy `require_roles` working for now so superadmin-only / global-scoped routes (like superadmin org management) can still gate on `User.role`

  **Implementation notes:**
  - Added `get_active_membership(...)` and `require_membership_roles(*allowed: UserRole)` in `backend/app/core/rbac.py` (alongside the existing `get_current_user_record` / `require_roles`).
  - `get_active_membership` reads the `X-Organization-Id` header via `Header(default=None, alias="X-Organization-Id")` typed as `int | None`. Resolution branches:
    1. Header present + matching `(user_id, org_id)` membership → return that row.
    2. Header present + no match + user is `superadmin` → synthesize a transient `UserOrganizationMembership` (constructor only — never `db.add`'d, never committed) with `role=superadmin`. Lets superadmins act on any org without a per-org row.
    3. Header present + no match + non-superadmin → 403 `"Not a member of this organization"`.
    4. Header missing + user is `superadmin` → 400 `"X-Organization-Id required"` (forces explicit org choice for global-override callers).
    5. Header missing + exactly one membership → use it.
    6. Header missing + zero or multiple memberships → 400 `"X-Organization-Id required"`.
  - `require_membership_roles(*allowed: UserRole)` is a thin factory that depends on `get_active_membership` and 403s when `membership.role not in allowed` — semantically identical to `require_roles` but operating on the active membership's per-org role rather than the user's global `User.role`. So an `lp`-by-default user who is `admin` of Org B will pass `require_membership_roles(UserRole.admin)` when acting through Org B.
  - `require_roles` (the global-role gate) is left untouched — superadmin-only / global routes (e.g. `/organizations` superadmin management) continue to use it. This phase only adds the new dependency surface; router migration is the next task.
  - Lint clean (`make lint` → all green), tests green (`uv run pytest` → 161 passed including the existing `test_rbac.py` suite). Test coverage for the new dep itself comes in the later Phase 02 task `test_active_membership_dep.py` (per task list ordering).

- [x] Migrate every org-scoped router off `current_user.organization_id`:
  - For each file from the audit (`funds`, `fund_groups`, `fund_team_members`, `investors`, `investor_contacts`, `commitments`, `capital_calls`, `distributions`, `documents`, `communications`, `tasks`, `notifications`, `dashboard`, `audit_logs`, `users`):
    - Replace the `current_user: User = Depends(require_roles(...))` pattern with `membership: UserOrganizationMembership = Depends(require_membership_roles(...))` where appropriate
    - Use `membership.organization_id` for query scoping
    - Use `membership.role` for in-org authorization checks
    - Where a route legitimately operates outside an org (e.g. `/users/me`, `/users/me` patches, list-my-memberships), keep it on `get_current_user_record`
  - The `/users` invite endpoint and `/users/{id}/role` endpoint will move to membership-based management in Phase 04 — for now, leave them but make them noop-safely on superadmins (return 400 with a clear message saying invitations are the new path)

  **Implementation notes:**
  - **Repositories** (`fund_repository`, `investor_repository`, `commitment_repository`, `capital_call_repository`, `distribution_repository`, `document_repository`, `communication_repository`, `task_repository`): swapped the `User`-based `list_for_user`/`user_can_view`/`user_can_manage` API for `list_for_membership`/`membership_can_view`/`membership_can_manage` taking `UserOrganizationMembership`. Internal branching is now `if membership.role in (admin, fund_manager, superadmin): scope by membership.organization_id; else: contact-based path filtered by membership.user_id`. The legacy admin "see all orgs" branch is gone — admin is per-org now, exactly as the Phase 02 design intends.
  - **Routers migrated to `require_membership_roles(admin, fund_manager, superadmin)` for write paths and `get_active_membership` for read paths**: `funds`, `fund_groups`, `fund_team_members`, `investors`, `investor_contacts`, `commitments` (incl. `fund_commitments_router`, `investor_commitments_router`), `capital_calls` (incl. `fund_capital_calls_router`), `distributions` (incl. `fund_distributions_router`), `documents`, `communications` (incl. `fund_communications_router`), `tasks` (incl. `fund_tasks_router`).
  - **`dashboard` router**: takes `Header(X-Organization-Id)` and `current_user` directly, then resolves a membership via a local `_resolve_active_membership` helper that returns `None` for "no header + zero memberships" so the dashboard can keep its "no org = empty zeros" UX (the existing `test_user_without_organization_returns_zeros` and `test_no_user_row_returns_zeros` still pass). Header-present + non-member + non-superadmin still raises 403; superadmin without a header still 400s; multi-membership without a header still 400s.
  - **`/users` invite endpoint**: now takes `require_membership_roles(admin, fund_manager, superadmin)`. If the resolved membership is a synthesized superadmin row (no `id`), returns 400 with `"Use POST /organizations/{id}/memberships to add users (Phase 04)"`. Otherwise the legacy seeding from `membership.organization_id` still runs.
  - **`/users` GET (list)** and **`/users/{id}` PATCH (update)**: also moved to `require_membership_roles`. The PATCH cross-org guard now compares `target.organization_id` against `membership.organization_id`, with an exemption for superadmin (who can act on any org via the header).
  - **`/users/{id}/role` PATCH**: kept on `require_roles(admin, superadmin)` per the task list — global role-update is still a global-role gate. Added `superadmin` to the allow-list for forward compatibility.
  - **`/users/me` GET/PATCH**: deliberately stay on `get_current_user_record` (no org context required).
  - **`notifications` router**: reviewed, no changes needed — endpoints were already user-scoped via `current_user.id` and never read `organization_id`.
  - **`audit_logs` router**: reviewed, kept on `require_roles(UserRole.admin)` (global admin gate). Phase 02 task list does not call out a migration for this; revisit in a later phase if audit-log scoping needs to become per-org.
  - **Test fixture migration**: every `_seed_user(... organization_id=...)` helper in the test suite now also creates a matching `UserOrganizationMembership` row, mirroring what `bulk_seed_from_legacy_user_org_id` does in production. Touched files: `test_funds_api.py`, `test_investors_api.py`, `test_capital_calls_api.py`, `test_commitments_api.py`, `test_distributions_api.py`, `test_documents_api.py`, `test_communications_api.py`, `test_tasks_api.py`, `test_notifications_api.py`, `test_users_api.py`, `test_dashboard.py`. In `test_dashboard.py` the previously platform-wide admin test (`test_admin_sees_aggregates_across_all_organizations`) was rewritten as `test_admin_with_multi_org_memberships_scopes_per_active_org` — now validates that an admin with memberships in two orgs sees only the org chosen via `X-Organization-Id`, which is the new per-org admin contract.
  - Gate trio green: `make openapi` (regenerated `openapi.json` + `frontend/src/lib/schema.d.ts`), `make lint`, `make test` (161 passed).

- [x] Add a `/users/me/memberships` route returning `list[MembershipRead]`:
  - Create or extend `backend/app/routers/users.py` with `GET /me/memberships`
  - The frontend will use this to populate the org switcher in Phase 05

  **Implementation notes:**
  - Added `GET /users/me/memberships` to `backend/app/routers/users.py` (placed adjacent to the other `/me` endpoints). Returns `list[MembershipRead]` — each item carries the full nested `OrganizationRead` payload so the frontend org switcher can render names without a follow-up fetch.
  - Implementation simply calls `UserOrganizationMembershipRepository(db).list_for_user(current_user.id)`. Auth comes from the existing router-level `Depends(get_current_user)` in `main.py` plus the route-local `Depends(get_current_user_record)` to materialize the `User` row. No `X-Organization-Id` header involvement — this endpoint is intentionally non-org-scoped (it's *the* lookup the org switcher uses to discover which orgs a user can switch into).
  - Route ordering note: declared `/me/memberships` after `/me` PATCH and before the `/{user_id}` PATCH route, so FastAPI's path matcher picks the literal `/me/memberships` first instead of treating `me` as a `{user_id}` path param.
  - Gate trio green: `make openapi` (regenerated `backend/openapi.json` + `frontend/src/lib/schema.d.ts` — the new path is exposed to the frontend client), `make lint` (clean), `make test` (161 passed). Phase-02-task-5 will add a dedicated `test_users_memberships_route.py` for this endpoint; not adding speculative tests here per task ordering.

- [ ] Add tests for the new dependency and the migrated routers:
  - `backend/tests/test_active_membership_dep.py`: header missing + single membership = resolves; header present + match = resolves; header present + no match + non-superadmin = 403; header present + superadmin = synthesized membership; header missing + superadmin = 400
  - For one already-tested router (e.g. `funds`), update the existing test to pass `X-Organization-Id` and assert cross-org leakage is blocked
  - `backend/tests/test_users_memberships_route.py`: returns memberships including org payload and per-org role

- [ ] Run the gate trio and fix any breakage:
  - `make openapi` (the new header param + memberships route change the schema)
  - `make lint`
  - `make test`
