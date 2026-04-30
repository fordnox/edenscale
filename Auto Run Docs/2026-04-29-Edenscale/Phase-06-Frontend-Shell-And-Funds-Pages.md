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

- [ ] Improve the AppShell layout from Phase 01:
  - Add `Topbar.tsx` (search input, notifications bell that links to `/notifications`, user menu pulled from `GET /users/me`)
  - Update `AppShell.tsx` to render `<Sidebar />` + a column with `<Topbar />` and `<main><Outlet /></main>`
  - Keep the EdenScale typography and parchment background classes from Phase 01

- [ ] Port the Funds list page:
  - Create `frontend/src/pages/FundsPage.tsx` modeled on `edenscale/src/pages/FundsPage.tsx` but using `useApiQuery("/funds")` for data
  - Fund row links to `/funds/${id}` via `react-router-dom` `Link`
  - Add a "New fund" button that opens a `FundCreateDialog` (Radix Dialog) and posts to `POST /funds`; on success, invalidate the `["funds"]` query
  - Empty state: card with "No funds yet" + the new fund button
  - Replace the placeholder `/funds` route in `App.tsx` with this page

- [ ] Port the Fund Detail page:
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

- [ ] Add a shared StatusPill component:
  - `frontend/src/components/ui/StatusPill.tsx` — accepts `kind` (`fund` | `commitment` | `capital_call` | `distribution` | `task` | `notification`) and `value` (the enum string from the API), renders the right color pill using the `--status-*` and `--conifer-*` tokens. Centralize the kind→color map here so all pages stay consistent

- [ ] Add an in-page navigation pattern that reads/writes `?tab=` query params so refresh preserves tab state on Fund Detail and similar future pages

- [ ] Confirm the build:
  - From `frontend/`, run `pnpm run lint` (`tsc --noEmit`) and resolve type errors
  - Manually verify in the browser: load `/funds`, create a fund, click into the fund, see the empty Commitments / Calls / Distributions tables render gracefully

- [ ] Run repo-level gates:
  - `make lint` and `make test` (backend should be unaffected)
