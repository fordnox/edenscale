# Phase 06: Superadmin Console (Frontend)

This phase adds the `/superadmin/*` UI section: a route family that only superadmins can access, with pages to list/create organizations, drill into one org and manage its admins, and toggle org active status. The Sidebar gains a "Superadmin" group when the signed-in user is a superadmin. Layout, components, and visual style match the existing app — no new design system pieces.

## Tasks

- [ ] Read prior art before writing:
  - `frontend/src/pages/OrganizationSettingsPage.tsx` (closest analogue — re-use its Card/CardSection/DataTable layout and InviteUserDialog idiom)
  - `frontend/src/components/RequireRole.tsx` and the new `useActiveMembership` from Phase 05
  - `frontend/src/App.tsx` for the routing pattern inside `AppShell`
  - `frontend/src/hooks/useNavItems.ts` for the nav definition shape

- [ ] Add a `RequireSuperadmin` guard:
  - Create `frontend/src/components/RequireSuperadmin.tsx` analogous to `RequireRole.tsx` — reads `useApiQuery("/users/me")`, if `me.role !== "superadmin"` renders a 403 Card with a "Back to dashboard" link, else renders children
  - Use this on every superadmin route below

- [ ] Create the superadmin pages:
  - `frontend/src/pages/superadmin/SuperadminOrganizationsPage.tsx` — list view at `/superadmin/organizations`. Table of orgs with `name`, `type`, `is_active`, `member_count`, `created_at`; row click → detail page; top-right "Create organization" button opens a dialog
  - `frontend/src/components/superadmin/CreateOrganizationDialog.tsx` — form: name, type (Select), legal_name, founding admin email, founding admin role (default `admin`). Submit hits `POST /superadmin/organizations`; on success, toast + `queryClient.invalidateQueries(["/superadmin/organizations"])` + close
  - `frontend/src/pages/superadmin/SuperadminOrganizationDetailPage.tsx` at `/superadmin/organizations/:organizationId` — shows org details (read-only firm metadata + edit-on-click name/legal_name), members table from `GET /superadmin/organizations/{id}/members`, and a "Disable organization" / "Enable organization" button calling the corresponding endpoints
  - `frontend/src/components/superadmin/AssignAdminDialog.tsx` — embedded in detail page; lets a superadmin add another admin by email or selecting from the existing user list (this hits `POST /superadmin/organizations/{id}/admins`)

- [ ] Wire the routes in `App.tsx`:
  ```
  <Route path="/superadmin/organizations" element={<RequireSuperadmin><SuperadminOrganizationsPage /></RequireSuperadmin>} />
  <Route path="/superadmin/organizations/:organizationId" element={<RequireSuperadmin><SuperadminOrganizationDetailPage /></RequireSuperadmin>} />
  ```
  Keep them inside the `<AppShell />` route group so the sidebar/topbar stays consistent.

- [ ] Extend the Sidebar nav for superadmins:
  - In `frontend/src/hooks/useNavItems.ts`, when `useApiQuery("/users/me").data?.role === "superadmin"`, prepend a top-level "Superadmin" section header + nav items: "Organizations" → `/superadmin/organizations". Use a divider between superadmin and regular nav. Reuse the existing nav-item shape (no new section components).

- [ ] Update the Topbar org switcher (built in Phase 05) so superadmins see a "Manage all organizations →" link at the bottom of the dropdown that routes to `/superadmin/organizations`. If you already added this in Phase 05, just verify the link works.

- [ ] Type checks + browser smoke test:
  - `cd frontend && pnpm run lint`
  - Start both servers, sign in as a superadmin (use the Phase 01 CLI to promote your local Hanko user), verify the superadmin nav appears, create an org with a founding admin, switch to that org via the Topbar switcher, then sign in as the founding admin in a private window and confirm they see the new org in their switcher
  - Note any UX rough edges in `Auto Run Docs/2026-04-30-Edenscale-2/Working/superadmin-console-followups.md` for the user to triage
