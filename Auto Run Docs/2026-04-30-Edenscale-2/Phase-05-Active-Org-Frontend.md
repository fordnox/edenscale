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

- [ ] Update the API client middleware to attach `X-Organization-Id`:
  - In `frontend/src/lib/api.ts`, extend `myMiddleware.onRequest` to read the active org id from a small `getActiveOrganizationId()` helper (export this from `contexts/ActiveOrganizationContext.tsx` or a sibling `lib/activeOrg.ts` that mirrors `localStorage`). The header must be set BEFORE the body is sent and must NOT be set if no active org is selected
  - Make sure middleware order is: auth header → active org header → response handling

- [ ] Add the org switcher to the Topbar:
  - Insert a `DropdownMenu` to the LEFT of the bell icon in `frontend/src/components/layout/Topbar.tsx`
  - Trigger shows the active org's name (truncated) and a small chevron; if the user has only one membership, render the org name as static text (no dropdown)
  - Dropdown items list every membership with `org.name` and a small role badge (`Admin`, `Fund manager`, `LP`, `Superadmin`)
  - For superadmins, append a "View all organizations →" item that routes to `/superadmin/organizations` (built in Phase 06)
  - Selecting a different org calls `setActiveOrganizationId(id)`, then `queryClient.invalidateQueries()` to refetch all data under the new scope
  - Reuse `Topbar.tsx`'s existing visual idiom — no new design tokens

- [ ] Update role-aware UI to use the active membership's role:
  - `frontend/src/hooks/useNavItems.ts` — switch from `me.role` to `activeMembership?.role`. Superadmins (no membership) get a superadmin-flavored nav (introduced in Phase 06). For now, fall back gracefully if `activeMembership` is null
  - `frontend/src/components/RequireRole.tsx` — accept role from active membership; keep prop API stable (`allowed: UserRole[]`)
  - The OrganizationSettingsPage `meQuery.data.organization_id` reference must move to `activeMembership.organization_id`; do a quick grep for `me.organization_id` and `me?.organization_id` in `frontend/src/` and update each

- [ ] Add an empty state for users with zero memberships:
  - When `memberships.length === 0` AND the user is NOT a superadmin, render a full-page placeholder inside `AppShell` saying "You haven't been invited to an organization yet. Check your email for a pending invitation, or contact your administrator." Do NOT block superadmins — they get redirected to `/superadmin/organizations` instead

- [ ] Tests:
  - If the project has frontend tests configured (check `frontend/package.json` and `frontend/vitest.config.*`), add at least:
    - `ActiveOrganizationContext.test.tsx`: localStorage hydrate, default-to-first-membership, setActiveOrganizationId persists
    - A snapshot or render test for the Topbar showing single-org vs multi-org states
  - If frontend tests are not configured, skip but note this in a brief comment in the provider file: `// TODO: tests pending frontend test harness setup` — and definitely do not invent a new harness

- [ ] Run `cd frontend && pnpm run lint` (which is `tsc --noEmit`) and fix typing issues. Then start `make start-backend` and `make start-frontend` and:
  - Sign in
  - Verify the org switcher renders
  - Verify network requests now include the `X-Organization-Id` header (DevTools)
  - Verify switching org refetches data
  - Report any UI gaps to the user explicitly — claim of success requires actual browser verification, not just type checks
