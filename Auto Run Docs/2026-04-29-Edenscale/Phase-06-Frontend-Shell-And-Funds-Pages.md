# Phase 06: Frontend — Shell, Funds, And Fund Detail

This phase ports the prototype's app shell (sidebar + topbar + protected routing) into the production frontend and wires the Funds list and Fund Detail pages to live API data via the generated OpenAPI client. After this phase, a logged-in user can navigate the full primary nav, see real funds, click into a fund, and view its KPIs, commitments, capital calls, and distributions.

## Tasks

- [ ] Read the existing frontend before adding new code:
  - Re-read `frontend/src/App.tsx`, `frontend/src/layouts/AppShell.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/Topbar.tsx`, `frontend/src/components/ui/*`, `frontend/src/lib/api.ts`, `frontend/src/lib/format.ts` from Phase 01
  - Read the prototype source files we're porting: `edenscale/src/pages/FundsPage.tsx`, `edenscale/src/pages/FundDetailPage.tsx`, `edenscale/src/data/mock.ts`, `edenscale/src/lib/router.ts`
  - List the methods on `frontend/src/lib/api.ts` and confirm `useQuery` is available via `@tanstack/react-query` (check `frontend/package.json`; if missing, add it and the `QueryClientProvider` wrapper in `main.tsx`)

- [ ] Establish data-fetching primitives the rest of the frontend phases will reuse:
  - Add `frontend/src/lib/queryClient.ts` exporting a configured `QueryClient` (5-minute staleTime, retry once)
  - Wrap `<App />` in `<QueryClientProvider>` in `frontend/src/main.tsx`
  - Add `frontend/src/hooks/useApiQuery.ts` and `useApiMutation.ts` thin wrappers over TanStack Query that take an OpenAPI path + params, return typed data via `schema.d.ts`, and surface errors via the existing `sonner` toast in `lib/api.ts` middleware

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
