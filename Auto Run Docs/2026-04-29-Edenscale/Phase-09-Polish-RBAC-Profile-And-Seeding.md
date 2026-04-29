# Phase 09: Polish — RBAC UI, Profile, Seed Data, And End-to-End Verification

This final phase focuses on the seams: a UI for editing the current user's profile and role display, role-aware sidebar (LPs see fewer items, fund_managers see everything), an admin-only Audit Log viewer, a seed script that produces a realistic demo dataset for screenshots and demos, and a full end-to-end smoke run. It also captures architecture decisions in structured Markdown so future contributors can navigate the codebase via a documentation graph.

## Tasks

- [ ] Re-read all prior phase documents to take stock of what is already shipped and avoid re-doing work; cross-reference with `git log` to see what was actually committed

- [ ] Build the user profile page:
  - Create `frontend/src/pages/ProfilePage.tsx` — current user info (read from `GET /users/me`), editable first_name / last_name / phone / title via `PATCH /users/me`
  - Show the user's role as a non-editable chip with explanatory text ("Roles are managed by your administrator")
  - Show the user's organization name and a link to organization settings if the user is admin or fund_manager
  - Mount at `/profile` and link from the Topbar user menu (replace any existing `UserProfilePage` if it duplicates)

- [ ] Add an Organization Settings page (admin + fund_manager only):
  - `frontend/src/pages/OrganizationSettingsPage.tsx` — edit organization name/legal_name/tax_id/website/description via `PATCH /organizations/{id}`
  - List team members with their roles; admin can change roles via `PATCH /users/{id}/role`, fund_manager can invite new users via `POST /users`
  - Mount at `/settings/organization` and gate via a `RequireRole` component

- [ ] Make the sidebar role-aware:
  - Read role from `GET /users/me` once (cached via TanStack Query)
  - LPs: hide Tasks management, hide global Capital Calls / Distributions list; show only Funds, Investors (read-only of self), Documents (filtered to their own), Letters, Notifications, Profile
  - fund_manager: full sidebar
  - admin: full sidebar plus an "Audit Log" entry
  - Implement as a `useNavItems()` hook returning the filtered list

- [ ] Build the Audit Log viewer (admin only):
  - `frontend/src/pages/AuditLogPage.tsx` — paginated table over `GET /audit-logs` with filters for `entity_type`, `action`, `user_id`, `date_from`, `date_to`
  - Click a row to expand the JSON metadata in a code block

- [ ] Add a backend seed script:
  - `backend/scripts/seed_demo.py` — idempotent script that creates: 1 fund_manager_firm + 2 investor_firm organizations, 1 admin + 2 fund_manager + 4 LP users (with `hanko_subject_id` left null and a deterministic email so a developer can claim them via Hanko), 2 fund groups, 4 funds across vintage years, 6 investors with primary contacts, 12 commitments, 3 capital calls (one fully paid, one partially paid, one scheduled), 2 distributions, 5 documents, 4 letters, 8 tasks, 6 notifications, and the resulting audit log entries
  - Add a Makefile target `make seed` that runs `cd backend && uv run python -m scripts.seed_demo`

- [ ] Capture architecture knowledge as structured Markdown for the project's docs graph:
  - Create `docs/architecture/system-overview.md` with YAML front matter (`type: reference`, `title: System Overview`, `created: 2026-04-29`, `tags: [architecture, fastapi, react]`) summarizing the two-service monorepo, OpenAPI contract, Hanko auth, RBAC layer; cross-link `[[API-Layering]]`, `[[Database-Schema]]`, `[[Frontend-Routing]]`
  - Create `docs/architecture/api-layering.md` describing the router → repository → model → schema convention with file-path examples
  - Create `docs/architecture/database-schema.md` summarizing the entity groups (orgs+users, funds+commitments, capital flows, supporting) with a textual ER diagram and links to `[[RBAC-Model]]`
  - Create `docs/architecture/rbac-model.md` documenting the three roles, the `require_roles` dependency, and the visibility rules per entity
  - Create `docs/architecture/frontend-routing.md` listing every route, layout, and the role gating per route
  - Create `docs/decisions/adr-001-rbac-via-hanko-jwt.md` (`type: analysis`, `tags: [auth, decision]`) capturing the choice to map Hanko subject → local User row + `role` enum and the alternative (Hanko custom claims) we did not pick
  - Create `docs/decisions/adr-002-storage-port-pattern.md` capturing the StoragePort abstraction and the LocalDevStorage default
  - Each file uses `[[wiki-link]]` syntax for cross-references

- [ ] Run a full end-to-end smoke pass:
  - Wipe the local DB, run `make upgrade`, then `make seed`
  - Start backend + frontend; log in as one of the seeded fund_manager users (claim the email via Hanko)
  - Walk every page: Dashboard → Funds → FundDetail → Investors → Capital Calls (record a payment) → Distributions (send a draft) → Documents (upload a file) → Letters (send a draft) → Tasks (complete one) → Notifications (mark read) → Profile → Organization Settings
  - Log out, log in as a seeded LP, confirm the sidebar is filtered and only the LP's commitments / docs / letters appear
  - Capture and fix any 4xx/5xx errors or broken UI states

- [ ] Final repo gates and lockdown:
  - Run `make openapi`, `make test`, `make lint` and resolve every finding
  - Run `frontend && pnpm run lint`
  - Confirm `git status` is clean apart from intended changes; the pre-commit checklist from `README.md` (test pass, lint pass, openapi sync) is satisfied
