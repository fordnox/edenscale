# Phase 05: Active Org Switcher (Frontend)

This phase wires the frontend to the new multi-org world. A new `ActiveOrganizationProvider` reads the user's memberships from `/users/me/memberships`, persists the chosen org id in `localStorage`, and exposes hooks (`useActiveOrganization`, `useActiveMembership`) consumed throughout the app. The `Topbar` gets an organization switcher dropdown. The API client middleware automatically attaches the `X-Organization-Id` header on every request. The Sidebar's role-based nav now reads from the active membership's role rather than the legacy `User.role`.

## Tasks

- [x] Read the existing frontend conventions before writing new code:
  - `frontend/src/lib/api.ts` (the openapi-fetch middleware — the new header attaches here)
  - `frontend/src/lib/hanko.ts` and `frontend/src/hooks/useAuth.ts`
  - `frontend/src/hooks/useApiQuery.ts` and `useApiMutation.ts` for the standard data-fetching wrappers
  - `frontend/src/components/layout/Topbar.tsx` and `Sidebar.tsx` (where the switcher and role chip live)
  - `frontend/src/hooks/useNavItems.ts` (currently keys off `me.role`)
  - `frontend/src/components/RequireRole.tsx`

  **Notes for subsequent tasks:**
  - `lib/api.ts` middleware order today is: auth header (onRequest) → response handling (onResponse) → error toast (onError). The active-org header should attach in `onRequest` AFTER the auth header.
  - `useApiQuery`/`useApiMutation` are thin wrappers over `@tanstack/react-query` that key on `[path, init]`; `queryClient.invalidateQueries()` (no args) will refetch all of them, which is what the org switch will need.
  - The role chip / role-gated nav lives in `Sidebar.tsx` (`SidebarBody`), not `Topbar.tsx`. `Topbar.tsx` currently has only a hamburger + search button — there is **no bell icon** despite the task description mentioning one. The switcher should land at the right edge of `Topbar` where the bell would have been; flag for the user when implementing.
  - `Sidebar.tsx` reads `role` from `useNavItems()` and uses it both for the tagline and the `admin`-only "Organization settings" item — both must move to `activeMembership?.role`.
  - `RequireRole.tsx` currently fetches `/users/me` itself and checks `me.role`; refactor to read from the active-org context, but keep the `allowed: readonly UserRole[]` prop API stable.
  - `getSessionToken()` in `lib/hanko.ts` reads from `document.cookie` synchronously — same pattern works for the new `getActiveOrganizationId()` helper if it mirrors `localStorage`.

- [x] Build the active-organization context:
  - Create `frontend/src/contexts/ActiveOrganizationContext.tsx` with a provider that:
    - Reads `/users/me/memberships` via `useApiQuery`
    - Stores the active `organization_id` in state, hydrated from `localStorage["edenscale.active_org_id"]`
    - On memberships load: if stored id matches a membership, keep it; else default to the first membership; if user has zero memberships, set to `null`
    - Persists changes back to `localStorage`
    - Exposes `{ memberships, activeMembership, activeOrganizationId, setActiveOrganizationId, isSuperadmin }` via context
  - Create `frontend/src/hooks/useActiveOrganization.ts` and `useActiveMembership.ts` that read from the context and throw clear errors if used outside the provider
  - Wrap `App.tsx` (inside the existing query client + auth providers, outside the routes) with `<ActiveOrganizationProvider>`

  **Notes from implementation:**
  - LocalStorage helpers extracted to a sibling `frontend/src/lib/activeOrg.ts` (`getActiveOrganizationId`, `setStoredActiveOrganizationId`) so the upcoming `lib/api.ts` middleware can read the active org id without importing React. The middleware task should import `getActiveOrganizationId` from `@/lib/activeOrg`.
  - `isSuperadmin` is derived by also fetching `/users/me` (alongside `/users/me/memberships`) and checking `meQuery.data?.role === "superadmin"`, since the user-level role lives on `UserRead`, not on memberships. Both queries use a 5-min `staleTime`, matching `useNavItems`.
  - Provider also exposes `isLoading` (true while either of the two queries is loading) — useful for the upcoming empty-state and switcher UI.
  - Reconcile effect runs after memberships load: drops a stored org id that no longer matches; falls back to the first membership; clears storage when memberships are empty.
  - Per the test-task note: added `// TODO: tests pending frontend test harness setup` to `ActiveOrganizationContext.tsx` (frontend has no vitest configured today).
  - `<ActiveOrganizationProvider>` wraps `<Routes>` inside `App.tsx`. Login page is also inside it; its memberships query returns 401 (silently — middleware already skips toasts on 401) until the user authenticates.

- [x] Update the API client middleware to attach `X-Organization-Id`:
  - In `frontend/src/lib/api.ts`, extend `myMiddleware.onRequest` to read the active org id from a small `getActiveOrganizationId()` helper (export this from `contexts/ActiveOrganizationContext.tsx` or a sibling `lib/activeOrg.ts` that mirrors `localStorage`). The header must be set BEFORE the body is sent and must NOT be set if no active org is selected
  - Make sure middleware order is: auth header → active org header → response handling

  **Notes from implementation:**
  - Imported `getActiveOrganizationId` from `@/lib/activeOrg` (the helper extracted in the prior task) and called it inside the existing `onRequest` after the auth-header logic. The header is only set when the helper returns a non-null id, so requests pre-login (or from a user with zero memberships) skip it cleanly.
  - Header value is `String(activeOrgId)` — the backend dependency parses the integer.
  - Pre-existing `tsc` errors in `OrganizationSettingsPage.tsx` and `ProfilePage.tsx` (the `superadmin` role missing from some `Record<UserRole, string>` maps) are unrelated to this change and are scoped for the next task ("Update role-aware UI to use the active membership's role").

- [x] Add the org switcher to the Topbar:
  - Insert a `DropdownMenu` to the LEFT of the bell icon in `frontend/src/components/layout/Topbar.tsx`
  - Trigger shows the active org's name (truncated) and a small chevron; if the user has only one membership, render the org name as static text (no dropdown)
  - Dropdown items list every membership with `org.name` and a small role badge (`Admin`, `Fund manager`, `LP`, `Superadmin`)
  - For superadmins, append a "View all organizations →" item that routes to `/superadmin/organizations` (built in Phase 06)
  - Selecting a different org calls `setActiveOrganizationId(id)`, then `queryClient.invalidateQueries()` to refetch all data under the new scope
  - Reuse `Topbar.tsx`'s existing visual idiom — no new design tokens

  **Notes from implementation:**
  - As flagged in the prior task's notes, there is no bell icon in `Topbar.tsx`. The switcher landed at the right edge of the header (where a bell would have lived), pushed there with `ml-auto`. The flex container's previous `justify-between` was replaced — with `ml-auto` on the switcher group, the existing children (hamburger on mobile, search on desktop) remain at their original positions. **User: confirm this placement matches the intended design before adding a bell icon later.**
  - Trigger styling mirrors the existing search button: same `h-9`, `rounded-xs`, hairline border, `hover:border-conifer-600` treatment. No new design tokens introduced.
  - Static-text branch (`memberships.length === 1 && !isSuperadmin`) renders the name without a border or chevron so it reads as a label, not an interactive control.
  - Superadmins always get the dropdown (even with 0 or 1 memberships) so the "View all organizations →" entry remains reachable. When a superadmin has zero memberships, the trigger label falls back to "All organizations".
  - Empty/non-superadmin case (zero memberships) renders nothing — the empty-state task that follows will handle that case in `AppShell`.
  - Active membership is highlighted with `bg-parchment-200` (matches the active nav item style in `Sidebar.tsx`); selecting the already-active org is a no-op so we don't trigger a needless `invalidateQueries()`.
  - Role badge uses inline `text-[10px] tracking-[0.06em] uppercase text-ink-500` rather than the `Badge` component, since `Badge` ships with a status dot and rounded-full pill that would have been too heavy inside a menu row.
  - `tsc --noEmit` passes for this change. The 3 pre-existing errors in `OrganizationSettingsPage.tsx` and `ProfilePage.tsx` (superadmin missing from `Record<UserRole, string>` maps) are unchanged and remain scoped for the "Update role-aware UI" task.

- [x] Update role-aware UI to use the active membership's role:
  - `frontend/src/hooks/useNavItems.ts` — switch from `me.role` to `activeMembership?.role`. Superadmins (no membership) get a superadmin-flavored nav (introduced in Phase 06). For now, fall back gracefully if `activeMembership` is null
  - `frontend/src/components/RequireRole.tsx` — accept role from active membership; keep prop API stable (`allowed: UserRole[]`)
  - The OrganizationSettingsPage `meQuery.data.organization_id` reference must move to `activeMembership.organization_id`; do a quick grep for `me.organization_id` and `me?.organization_id` in `frontend/src/` and update each

  **Notes from implementation:**
  - `useNavItems.ts` no longer fetches `/users/me` itself — it now consumes `useActiveOrganization()` and forwards its `isLoading` flag. `role` is `activeMembership?.role ?? null`. For superadmins (no membership), `navItemsForRole(null)` returns the default `FULL_ITEMS` set; the Phase 06 superadmin-flavored nav will replace this branch.
  - `RequireRole.tsx` dropped its own `useApiQuery("/users/me")` and now reads `activeMembership` + `isLoading` from `useActiveOrganization()`. Prop API (`allowed: readonly UserRole[]`) unchanged. Superadmins with no active membership will fall to the deny branch — that's acceptable because Phase 06 routes them to `/superadmin/...` and existing role-gated pages (`/settings/organization`, `/audit-log`) are scoped to per-org admins anyway.
  - `Sidebar.tsx` already reads `role` from `useNavItems()` so the role chip / "Organization settings" item now follow the active membership automatically — no direct edit needed.
  - `OrganizationSettingsPage.tsx`: `orgId`, `isAdmin`, `isFundManager` all moved to `activeMembership`. Kept `meQuery` because `me.id` is still used for the "you cannot change your own role" guard. Loading guard now also waits on `isMembershipLoading`. `usersQuery.enabled` switched from `me !== undefined && ...` to `activeMembership !== null && ...`.
  - `ProfilePage.tsx`: `orgId` moved to `activeMembership.organization_id`. `canManageOrg` now reads `activeMembership.role`. The "Role & access" badge and description use `displayRole = activeMembership?.role ?? me?.role` so superadmins (no membership) still see a meaningful label; added an empty-state for the rare null case. `meQuery` retained — still needed for first/last name, phone, title editing.
  - Resolved the pre-existing `tsc` errors in both pages by adding `superadmin` entries to the `Record<UserRole, string>` maps (`ROLE_LABELS` in both, plus `ROLE_DESCRIPTIONS` in ProfilePage). The role `Select` dropdowns continue to whitelist only `["admin", "fund_manager", "lp"]` so superadmin remains unsettable through the UI.
  - `cd frontend && pnpm run lint` now passes with zero errors.

- [x] Add an empty state for users with zero memberships:
  - When `memberships.length === 0` AND the user is NOT a superadmin, render a full-page placeholder inside `AppShell` saying "You haven't been invited to an organization yet. Check your email for a pending invitation, or contact your administrator." Do NOT block superadmins — they get redirected to `/superadmin/organizations` instead

  **Notes from implementation:**
  - Added the empty-state branch directly in `frontend/src/layouts/AppShell.tsx` rather than a new component — only one call site, no need to abstract.
  - Reuses the existing `EmptyState` + `Card` primitives (mirrors the `RequireRole.tsx` pattern). The Mail icon was chosen because the body copy references checking email; matches `LettersPage.tsx`'s `strokeWidth={1.25}` convention.
  - Title is "No organization yet" with the spec'd body copy. Wrapped the card in a centered flex container (`items-center justify-center`, `max-w-xl`) so it reads as a full-page placeholder rather than a top-of-page banner.
  - Gated on `!isLoading && memberships.length === 0 && !isSuperadmin` so we don't flash the empty state during the initial `/users/me` + `/users/me/memberships` load. Superadmins fall through to the regular `<Outlet />` (Phase 06 will add their dedicated routing).
  - Sidebar + Topbar remain visible — they sit outside the `<main>` swap. This means a no-org user still sees the sign-out menu in the sidebar, which is desirable. The sidebar's role-aware nav items still render (since `navItemsForRole(null)` returns the default set), but clicking them just bounces back to the empty state, which is acceptable for this edge case.
  - `pnpm run lint` (`tsc --noEmit`) passes.

- [x] Tests:
  - If the project has frontend tests configured (check `frontend/package.json` and `frontend/vitest.config.*`), add at least:
    - `ActiveOrganizationContext.test.tsx`: localStorage hydrate, default-to-first-membership, setActiveOrganizationId persists
    - A snapshot or render test for the Topbar showing single-org vs multi-org states
  - If frontend tests are not configured, skip but note this in a brief comment in the provider file: `// TODO: tests pending frontend test harness setup` — and definitely do not invent a new harness

  **Notes from implementation:**
  - Confirmed no frontend test harness: `frontend/package.json` has no `test` script, no `vitest`/`jest`/`@testing-library/*` dependencies, and no `vitest.config.*` files exist. The only test/lint command is `pnpm run lint` (`tsc --noEmit`).
  - Per spec, skipping test creation. The required `// TODO: tests pending frontend test harness setup` comment already exists at `frontend/src/contexts/ActiveOrganizationContext.tsx:17` (added during the provider task).
  - No code changes for this task — verification only.

- [ ] Run `cd frontend && pnpm run lint` (which is `tsc --noEmit`) and fix typing issues. Then start `make start-backend` and `make start-frontend` and:
  - Sign in
  - Verify the org switcher renders
  - Verify network requests now include the `X-Organization-Id` header (DevTools)
  - Verify switching org refetches data
  - Report any UI gaps to the user explicitly — claim of success requires actual browser verification, not just type checks
