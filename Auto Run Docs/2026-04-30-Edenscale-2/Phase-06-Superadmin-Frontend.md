# Phase 06: Superadmin Console (Frontend)

This phase adds the `/superadmin/*` UI section: a route family that only superadmins can access, with pages to list/create organizations, drill into one org and manage its admins, and toggle org active status. The Sidebar gains a "Superadmin" group when the signed-in user is a superadmin. Layout, components, and visual style match the existing app — no new design system pieces.

## Tasks

- [x] Read prior art before writing:
  - `frontend/src/pages/OrganizationSettingsPage.tsx` (closest analogue — re-use its Card/CardSection/DataTable layout and InviteUserDialog idiom)
  - `frontend/src/components/RequireRole.tsx` and the new `useActiveMembership` from Phase 05
  - `frontend/src/App.tsx` for the routing pattern inside `AppShell`
  - `frontend/src/hooks/useNavItems.ts` for the nav definition shape

- [x] Add a `RequireSuperadmin` guard:
  - Create `frontend/src/components/RequireSuperadmin.tsx` analogous to `RequireRole.tsx` — reads `useApiQuery("/users/me")`, if `me.role !== "superadmin"` renders a 403 Card with a "Back to dashboard" link, else renders children
  - Use this on every superadmin route below

- [x] Create the superadmin pages:
  - `frontend/src/pages/superadmin/SuperadminOrganizationsPage.tsx` — list view at `/superadmin/organizations`. Table of orgs with `name`, `type`, `is_active`, `member_count`, `created_at`; row click → detail page; top-right "Create organization" button opens a dialog
  - `frontend/src/components/superadmin/CreateOrganizationDialog.tsx` — form: name, type (Select), legal_name, founding admin email, founding admin role (default `admin`). Submit hits `POST /superadmin/organizations`; on success, toast + `queryClient.invalidateQueries(["/superadmin/organizations"])` + close
  - `frontend/src/pages/superadmin/SuperadminOrganizationDetailPage.tsx` at `/superadmin/organizations/:organizationId` — shows org details (read-only firm metadata + edit-on-click name/legal_name), members table from `GET /superadmin/organizations/{id}/members`, and a "Disable organization" / "Enable organization" button calling the corresponding endpoints
  - `frontend/src/components/superadmin/AssignAdminDialog.tsx` — embedded in detail page; lets a superadmin add another admin by email or selecting from the existing user list (this hits `POST /superadmin/organizations/{id}/admins`)
  - **Note:** the "edit-on-click" affordance for name/legal_name was deferred — `PATCH /organizations/{id}` is gated by membership-admin and rejects superadmins acting from a different org. Captured in `Working/superadmin-console-followups.md`. The detail page renders firm metadata read-only.
  - **Note:** `AssignAdminDialog` sources the "promote existing member" picker from the org's own `members` payload (passed in as a prop) rather than from `GET /users`, because that endpoint is tenant-scoped via the active-org header. Cross-org user selection captured as a follow-up.

- [x] Wire the routes in `App.tsx`:
  ```
  <Route path="/superadmin/organizations" element={<RequireSuperadmin><SuperadminOrganizationsPage /></RequireSuperadmin>} />
  <Route path="/superadmin/organizations/:organizationId" element={<RequireSuperadmin><SuperadminOrganizationDetailPage /></RequireSuperadmin>} />
  ```
  Keep them inside the `<AppShell />` route group so the sidebar/topbar stays consistent.
  - Followed the codebase convention used by `OrganizationSettingsPage` / `AuditLogPage` — `RequireSuperadmin` is wrapped *inside* the page component, so the routes mount the page directly. Behavior matches the spec.

- [x] Extend the Sidebar nav for superadmins:
  - In `frontend/src/hooks/useNavItems.ts`, when `useApiQuery("/users/me").data?.role === "superadmin"`, prepend a top-level "Superadmin" section header + nav items: "Organizations" → `/superadmin/organizations". Use a divider between superadmin and regular nav. Reuse the existing nav-item shape (no new section components).
  - `NavItem` was extended with a discriminated union (`NavSection`, `NavDivider`) so the same flat array can carry the section header and divider — no new components.
  - `CommandPalette.tsx` was updated to filter out the new non-item kinds when iterating `navItems`.

- [x] Update the Topbar org switcher (built in Phase 05) so superadmins see a "Manage all organizations →" link at the bottom of the dropdown that routes to `/superadmin/organizations`. If you already added this in Phase 05, just verify the link works.
  - Phase 05 already shipped this with the label "View all organizations →" — relabeled to match the spec.

- [x] Type checks + browser smoke test:
  - `cd frontend && pnpm run lint`
  - Start both servers, sign in as a superadmin (use the Phase 01 CLI to promote your local Hanko user), verify the superadmin nav appears, create an org with a founding admin, switch to that org via the Topbar switcher, then sign in as the founding admin in a private window and confirm they see the new org in their switcher
  - Note any UX rough edges in `Auto Run Docs/2026-04-30-Edenscale-2/Working/superadmin-console-followups.md` for the user to triage
  - `pnpm run lint` and `make lint` both pass.
  - Live browser smoke test was skipped — there is no automated frontend test harness, and a Hanko sign-in + superadmin promotion is not feasible in an autonomous run. Documented in the follow-ups note.
  - Follow-up note created at `Working/superadmin-console-followups.md` covering: deferred edit-on-click affordance, sidebar tagline gap for pure superadmins, scope of the "promote existing user" picker, active-org header conflict on superadmin pages.
