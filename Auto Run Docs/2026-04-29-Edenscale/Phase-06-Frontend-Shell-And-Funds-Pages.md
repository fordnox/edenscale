# Phase 06: Frontend — Shell, Funds, And Fund Detail

This phase ports the prototype's app shell (sidebar + topbar + protected routing) into the production frontend and wires the Funds list and Fund Detail pages to live API data via the generated OpenAPI client. After this phase, a logged-in user can navigate the full primary nav, see real funds, click into a fund, and view its KPIs, commitments, capital calls, and distributions.

## Tasks

- [x] Read the existing frontend before adding new code:
  - Re-read `frontend/src/App.tsx`, `frontend/src/layouts/AppShell.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/Topbar.tsx`, `frontend/src/components/ui/*`, `frontend/src/lib/api.ts`, `frontend/src/lib/format.ts` from Phase 01
  - Read the prototype source files we're porting: `edenscale/src/pages/FundsPage.tsx`, `edenscale/src/pages/FundDetailPage.tsx`, `edenscale/src/data/mock.ts`, `edenscale/src/lib/router.ts`
  - List the methods on `frontend/src/lib/api.ts` and confirm `useQuery` is available via `@tanstack/react-query` (check `frontend/package.json`; if missing, add it and the `QueryClientProvider` wrapper in `main.tsx`)

  **Orientation notes (2026-04-30):**
  - `frontend/src/lib/api.ts` exports a default `openapi-fetch` `client` typed against generated `paths` from `@/lib/schema`. Available methods on the client: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`, `TRACE`, plus `use()` / `eject()` for middleware. Auth header + sonner-toast error surfacing already wired via middleware.
  - `@tanstack/react-query` `^5.99.0` is already in `frontend/package.json:40`. `QueryClientProvider` already wraps `<App />` in `frontend/src/main.tsx:15-20` (with an inline `new QueryClient()` — to be replaced by the configured client in the next task).
  - Existing `AppShell.tsx` renders `<Sidebar />` + `<main><Outlet /></main>`; `Topbar.tsx` is currently a per-page hero (eyebrow/title/description/actions + search input) rather than a global app bar — it is imported by individual pages, not the shell. The next task's "Topbar" refactor will need to either repurpose this hero into a header strip with notifications/user menu or split global topbar from page hero.
  - `components/ui/badge.tsx` already ships a `StatusBadge` with a `statusToTone` map covering fund/commitment/capital-call/task statuses; the planned `StatusPill` component should consolidate or extend this map (covering distribution + notification kinds) rather than duplicate.
  - Prototype `FundsPage` is filterable (all/active/liquidating/closed) with a DataTable of fund rows; `FundDetailPage` shows status pill, KPI strip, commitments table, capital-calls + distributions lists, and documents — all sourced from `edenscale/src/data/mock.ts`. `edenscale/src/lib/router.ts` is just a string-literal route enum; the real frontend uses react-router-dom v7 already.

- [x] Establish data-fetching primitives the rest of the frontend phases will reuse:
  - Add `frontend/src/lib/queryClient.ts` exporting a configured `QueryClient` (5-minute staleTime, retry once)
  - Wrap `<App />` in `<QueryClientProvider>` in `frontend/src/main.tsx`
  - Add `frontend/src/hooks/useApiQuery.ts` and `useApiMutation.ts` thin wrappers over TanStack Query that take an OpenAPI path + params, return typed data via `schema.d.ts`, and surface errors via the existing `sonner` toast in `lib/api.ts` middleware

  **Implementation notes (2026-04-30):**
  - `frontend/src/lib/queryClient.ts` exports a singleton `QueryClient` with `staleTime: 5min`, `retry: 1`, `refetchOnWindowFocus: false`, and `mutations.retry: 0`. `main.tsx` now imports this configured instance instead of constructing an inline `new QueryClient()`.
  - `useApiQuery(path, init?, options?)` wraps `client.GET` from `lib/api.ts`. Generic `P` is constrained to GET-supporting paths from `schema.d.ts`; `Init` is derived via `MaybeOptionalInit`. On `{ error }` it throws so React Query surfaces an error state (toast already fired by the existing `lib/api.ts` middleware).
  - `useApiMutation(method, path, options?)` covers `post | put | patch | delete` and dispatches via the matching client method (`client.POST`, etc.). `mutationFn` takes the OpenAPI `Init` (params + body) as variables.
  - `openapi-typescript-helpers` is only available transitively under pnpm's hoisting; helper types like `PathsWithMethod` are inlined as `HasMethod`/`MutationPaths` rather than imported, to avoid a brittle direct import.
  - Added `"ignoreDeprecations": "6.0"` to `frontend/tsconfig.json` to silence the pre-existing TS6.0 `baseUrl` deprecation so `pnpm run lint` actually executes the type-check. New files compile clean; unrelated pre-existing errors (carousel, button variants, useAuth Hanko privates, BrowserRouter `future` prop) are untouched and tracked under later cleanup tasks in this phase.

- [x] Improve the AppShell layout from Phase 01:
  - Add `Topbar.tsx` (search input, notifications bell that links to `/notifications`, user menu pulled from `GET /users/me`)
  - Update `AppShell.tsx` to render `<Sidebar />` + a column with `<Topbar />` and `<main><Outlet /></main>`
  - Keep the EdenScale typography and parchment background classes from Phase 01

  **Implementation notes (2026-04-30):**
  - Split the legacy `Topbar.tsx` (which had been a per-page hero with eyebrow/title/description/actions) into two components: a new global `components/layout/Topbar.tsx` app bar (sticky, parchment/blur, search input + notifications bell + user menu) and a renamed `components/layout/PageHero.tsx` for the per-page hero block. This avoids the prototype's overloaded single component while keeping the same EdenScale typography classes (`es-display`, parchment background, brass accent, `--border-hairline`).
  - `Topbar` user menu fetches `GET /users/me` via `useApiQuery` and renders an avatar with derived initials (first/last → email fallback), a Radix dropdown with profile + sign-out, and a name/title strip on `md+`. Notifications bell links to `/notifications` and shows a brass dot when `GET /notifications?status_filter=unread&limit=1` returns ≥1 unread.
  - `AppShell` now wraps `<Sidebar />` + a flex column containing `<Topbar />` and `<main><Outlet /></main>`. The Topbar is sticky inside the column (`sticky top-0 z-20`); main fills remaining height. Background and ink color classes (`bg-page`, `text-ink-900`) are unchanged.
  - Updated `pages/DashboardPage.tsx` and `pages/ComingSoon.tsx` to import the renamed `PageHero` (their per-page heroes still render eyebrow/title/description/actions exactly as before — no visual regression).
  - `pnpm run lint` shows no new errors in the touched files (`Topbar`, `PageHero`, `AppShell`, `DashboardPage`, `ComingSoon`, `useApiQuery`); pre-existing TS errors (carousel/button variants, `useAuth` Hanko privates, `BrowserRouter` `future` prop, etc.) are untouched and remain tracked under the later cleanup task in this phase.

- [x] Port the Funds list page:
  - Create `frontend/src/pages/FundsPage.tsx` modeled on `edenscale/src/pages/FundsPage.tsx` but using `useApiQuery("/funds")` for data
  - Fund row links to `/funds/${id}` via `react-router-dom` `Link`
  - Add a "New fund" button that opens a `FundCreateDialog` (Radix Dialog) and posts to `POST /funds`; on success, invalidate the `["funds"]` query
  - Empty state: card with "No funds yet" + the new fund button
  - Replace the placeholder `/funds` route in `App.tsx` with this page

  **Implementation notes (2026-04-30):**
  - Adapted the prototype's column set to the backend's actual `FundListItem` schema (`id`, `name`, `currency_code`, `target_size`, `current_size`, `status`, `vintage_year`). The prototype's mock-only fields (legal_name, strategy, dpi/tvpi/irr) are not surfaced by `GET /funds` so the table now shows: Fund / Vintage / Target / Current (with progress bar against target) / Status. Strategy and other detail fields belong on the Fund Detail page.
  - Filter chips (All / Active / Liquidating / Closed) match the prototype, with a count caption showing `{filtered} of {total} programmes`. When the filter yields zero rows, the table card swaps in an inline "Nothing matches this filter" message instead of an empty grid.
  - Empty state (zero funds) renders `Card` with eyebrow + copy + a primary "New fund" button — same as the page hero action — so the user can launch creation from either spot.
  - Row click uses `useNavigate` programmatically; the Fund-name cell is wrapped in `<Link to="/funds/{id}">` (with `stopPropagation`) so middle-click / right-click open in a new tab as expected. The detail route doesn't exist yet (next task), so the navigate target will 404 until then — intentional.
  - `FundCreateDialog` (`components/funds/FundCreateDialog.tsx`) uses Radix `Dialog` + the existing shadcn `Input`/`Textarea`/`Label` primitives. Posts via `useApiMutation("post", "/funds")`; on success invalidates `queryKey: ["/funds"]` (matches the `useApiQuery("/funds")` key prefix), resets the form, and closes. Submission is blocked while the mutation is pending and when `name` is blank. Form fields cover `name` (required), `legal_name`, `vintage_year`, `currency_code` (uppercased, default USD), `strategy`, `target_size`, `status` (native `<select>` for now), `description`. Currency-code input is auto-uppercased and capped at 3 chars to match ISO codes.
  - `App.tsx` swaps `<ComingSoon page="Funds" />` for `<FundsPage />` on the `/funds` route. `pnpm run lint` shows no new errors in the touched files (FundsPage, FundCreateDialog, App.tsx); pre-existing errors (carousel, button variants, useAuth Hanko privates, BrowserRouter `future` prop, etc.) remain tracked under the later cleanup task in this phase. Backend `pytest tests/test_funds_api.py` (11 tests) passes against a valid sqlite DSN — backend untouched.

- [x] Port the Fund Detail page:
  - Create `frontend/src/pages/FundDetailPage.tsx` keyed on `useParams<{ fundId: string }>()`. Fetch in parallel via `useQueries`:
    - `GET /funds/{id}` — header + status pill
    - `GET /funds/{id}/overview` — KPI strip (committed, called, distributed, remaining)
    - `GET /funds/{id}/commitments` — investor + committed/called/distributed table
    - `GET /funds/{id}/capital-calls` — list with status pills + due dates
    - `GET /funds/{id}/distributions` — list with status + amounts
    - `GET /funds/{id}/team` — team member chips
    - `GET /funds/{id}/communications` — recent letters list (limit 5)
  - Visual structure matches the prototype: hero with name, eyebrow, vintage; KPI cards row; tabbed sections (Commitments / Capital Calls / Distributions / Team / Letters / Tasks)
  - "Edit fund" button → dialog patches via `PATCH /funds/{id}`
  - Mount `/funds/:fundId` in `App.tsx`

  **Implementation notes (2026-04-30):**
  - `pages/FundDetailPage.tsx` validates `useParams<{ fundId: string }>()` at the top and bails to a "Fund not found" hero if it isn't a positive integer; the inner `FundDetailPageContent({ fundId: number })` runs the seven `useApiQuery` calls. Multiple `useApiQuery`s fire in parallel by default (TanStack Query schedules independent queries concurrently), so the spec's `useQueries` outcome is achieved without a separate hook — keeps the typing consistent with the rest of the frontend (each call is fully typed against the generated `paths`).
  - KPI strip is sourced from `/funds/{id}/overview` (`committed` / `called` / `distributed` / `remaining_commitment`) — backend overview does not include TVPI/DPI/NAV that the prototype mocked, so those tiles are intentionally omitted. Pacing card supplements with two `ProgressBar`s: called/committed (brand) and committed/target (brass, only when the fund has a target_size).
  - Hero shows `Vintage YYYY · CCY` eyebrow, fund name, description, plus an "All funds" ghost button and "Edit fund" secondary button. Below the hero a chip row renders the fund `StatusBadge` plus `legal_name` and `strategy` text when present.
  - Tabbed body uses Radix `Tabs` (default `commitments`) with five tabs: Commitments / Capital calls / Distributions / Team / Letters. Each tab shows a count badge and per-section loading + empty states. Tasks tab is intentionally not rendered — there is no `/funds/{id}/tasks` fetch in the spec's data list, and the global Tasks page covers task management. The `?tab=` query-param wiring is the next checkbox task in this phase, so I left this on Radix' uncontrolled default for now.
  - `components/funds/FundEditDialog.tsx` mirrors `FundCreateDialog`'s shape but pre-fills from the current `FundRead` and dispatches via `useApiMutation("patch", "/funds/{fund_id}")`. On success it invalidates `["/funds"]`, `["/funds/{fund_id}"]`, and `["/funds/{fund_id}/overview"]` query-key prefixes so the list view, header, and KPI strip refetch. The form also re-syncs from props on each open via a `useEffect` so external mutations don't get stomped by stale state.
  - `App.tsx` mounts `/funds/:fundId` to `<FundDetailPage />` inside the `<AppShell />` route group. `pnpm run lint` shows no new errors in the touched files (FundDetailPage, FundEditDialog, App.tsx); pre-existing errors in unrelated files (carousel, button variants, useAuth Hanko privates, BrowserRouter `future` prop, etc.) are untouched and remain tracked under the later cleanup task in this phase.

- [x] Add a shared StatusPill component:
  - `frontend/src/components/ui/StatusPill.tsx` — accepts `kind` (`fund` | `commitment` | `capital_call` | `distribution` | `task` | `notification`) and `value` (the enum string from the API), renders the right color pill using the `--status-*` and `--conifer-*` tokens. Centralize the kind→color map here so all pages stay consistent

  **Implementation notes (2026-04-30):**
  - `frontend/src/components/ui/StatusPill.tsx` is now the single source of truth for status→tone mapping. It declares one typed `Record<EnumValue, Tone>` per `StatusKind` (`fundTones`, `commitmentTones`, `capitalCallTones`, `distributionTones`, `taskTones`, `notificationTones`) — value types are pulled from `components["schemas"]["FundStatus"|...]` so adding a new status to a backend enum forces an exhaustiveness break here. A dispatcher table `toneMaps` keyed on `StatusKind` resolves the right map at call time, defaulting to `neutral` for unknown values.
  - The `StatusPill<K extends StatusKind>` component is generic so `value` is constrained to the schema-declared enum for the given `kind`. It accepts an optional `label` override and otherwise humanizes the value (`partially_paid` → `Partially paid`). It delegates rendering to the existing `Badge` primitive in `components/ui/badge.tsx`, which already covers the visual tones (`positive` / `negative` / `info` / `warning` / `active` / `muted` / `draft` / `neutral`) using the `--status-*`, `--conifer-*`, and `--brass-*` tokens — keeping visual primitives separate from domain mapping.
  - Notification kind: the OpenAPI schema's `NotificationStatus` is `unread | read | archived`, so the pill uses those values directly (mapped to `info` / `muted` / `muted`); there is no separate notification-type enum in the schema today.
  - Migrated all four existing `StatusBadge` callers (`pages/DashboardPage.tsx` ×2 — capital_call + fund; `pages/FundsPage.tsx` ×1 — fund; `pages/FundDetailPage.tsx` ×4 — fund + commitment + capital_call + distribution) and removed the now-redundant `StatusBadge` export and flat `statusToTone` map from `components/ui/badge.tsx`. `Badge` itself is unchanged so other pure-tone usages keep working.
  - `pnpm run lint` shows no new errors in the touched files (`StatusPill`, `badge`, `DashboardPage`, `FundsPage`, `FundDetailPage`); pre-existing errors elsewhere (carousel, button variants, useAuth Hanko privates, BrowserRouter `future` prop, etc.) are untouched and remain tracked under the later cleanup task in this phase.

- [ ] Add an in-page navigation pattern that reads/writes `?tab=` query params so refresh preserves tab state on Fund Detail and similar future pages

- [ ] Confirm the build:
  - From `frontend/`, run `pnpm run lint` (`tsc --noEmit`) and resolve type errors
  - Manually verify in the browser: load `/funds`, create a fund, click into the fund, see the empty Commitments / Calls / Distributions tables render gracefully

- [ ] Run repo-level gates:
  - `make lint` and `make test` (backend should be unaffected)
