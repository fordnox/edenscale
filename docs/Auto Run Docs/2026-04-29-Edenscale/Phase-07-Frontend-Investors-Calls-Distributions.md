# Phase 07: Frontend — Investors, Capital Calls, Distributions

This phase ports the LP- and capital-flow-focused pages from the prototype: Investors (list + detail panel), Capital Calls (list + drill-in), and Distributions (list + drill-in). All pages call the API via the generated client and use TanStack Query mutations for create / update / send / cancel actions, with optimistic invalidation on success.

## Tasks

- [x] Read the prototype pages we're porting before writing new code:
  - `edenscale/src/pages/InvestorsPage.tsx`, `edenscale/src/pages/CapitalCallsPage.tsx`, `edenscale/src/pages/DistributionsPage.tsx`
  - The shared `frontend/src/components/ui/StatusPill.tsx` from Phase 06 — reuse it instead of re-implementing color logic
  - The shared `useApiQuery` / `useApiMutation` hooks from Phase 06

  Notes from this read-pass:
  - **InvestorsPage prototype** is a flat list with KPI strip (investors-on-register, aggregate commitments, average position) and a `DataTable` of investor / type / primary contact / region / active funds / total committed. The new port turns this into a master/detail layout backed by `useApiQuery("/investors")` with Contacts and Commitments tabs in the right pane.
  - **CapitalCallsPage prototype** uses `Topbar` + `Card`/`CardSection` KPI strip (open / overdue / lifetime called / avg paid in) + a `DataTable` with `ProgressBar` for `paid_pct` and `StatusBadge` for status. The port should keep the KPI layout, replace `StatusBadge` with the shared `StatusPill` (`kind="capital_call"`), and add Radix `Select` filters for `fund_id` / `status` plus a side `Drawer` (Radix `Sheet`) for drill-in.
  - **DistributionsPage prototype** mirrors CapitalCalls structure exactly (KPI strip + table + status badges) — port should reuse the same drawer/dialog skeleton, only swapping endpoints to `/distributions` and the StatusPill `kind` to `"distribution"`.
  - **`StatusPill`** (`frontend/src/components/ui/StatusPill.tsx`) already maps every backend status enum (fund / commitment / capital_call / distribution / task / notification) to the right tone with a humanized label — no per-page color logic should be added.
  - **`useApiQuery`** keys queries as `[path, init]` and throws on `error`; **`useApiMutation`** wraps `client.{POST,PATCH,PUT,DELETE}` and re-throws on `error`. Both are typed by the OpenAPI `paths` map, so the path string drives request/response inference. Optimistic invalidation should target the same `[path, init]` tuples used by the list queries plus any nested keys (`["/funds/{fund_id}", { params: { path: { fund_id } } }]`, `["/dashboard"]`).

- [x] Port the Investors page:
  - Create `frontend/src/pages/InvestorsPage.tsx`. Master/detail layout: list on the left with `useApiQuery("/investors")`, detail panel on the right showing the selected investor's contacts, commitments, and recent activity
  - Master list columns: name, investor_type, accredited badge, total_committed (numeric tabular), fund_count
  - Detail panel tabs: Contacts, Commitments. Contacts tab shows a table with primary star icon and an "Add contact" form. Commitments tab shows the investor's commitment table with links to each fund
  - "New investor" button → `InvestorCreateDialog` posting to `POST /investors`
  - Inline edit primary contact via `PATCH /investors/{id}/contacts/{contactId}` and toggle is_primary
  - Replace the placeholder `/investors` route in `App.tsx`

  Implementation notes:
  - `InvestorCreateDialog` (`frontend/src/components/investors/InvestorCreateDialog.tsx`) follows the `FundCreateDialog` shape: name (required), investor_code, investor_type, accredited checkbox, notes. On success it invalidates `["/investors"]` and `["/dashboard"]`, fires a `sonner` toast, and lets the page auto-select the freshly created row via the `onCreated(id)` callback.
  - `InvestorsPage` uses a 2-column layout (`lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]`); the master list is always visible and rows are click-to-select with a `bg-parchment-100` highlight on the active row.
  - `InvestorDetailPanel` is keyed by investor id so its local form state resets when switching investors. It runs three queries: `/investors/{investor_id}` (header), `/investors/{investor_id}/contacts`, `/investors/{investor_id}/commitments`. Mutations target nested `[path, init]` query keys so only the affected investor's contact list refetches.
  - Primary toggle uses a Lucide `Star` button — filled brass when `is_primary` is true. Backend allows multiple primaries, so the UI just toggles the flag rather than enforcing exclusivity client-side.
  - `Add contact` form: when the investor has no contacts yet, the new contact is auto-marked `is_primary: true`; otherwise the new contact is added without disturbing the existing primary. Form fields reset only on success.
  - Commitments tab links each row to `/funds/{fund.id}` and uses `StatusPill kind="commitment"` so colour logic stays in the shared component.

- [x] Port the Capital Calls page:
  - Create `frontend/src/pages/CapitalCallsPage.tsx` listing all calls via `useApiQuery("/capital-calls")` with filters `?fund_id`, `?status` exposed as Radix Select dropdowns. Table columns: fund, title, due_date, amount, status pill, paid % progress bar
  - Drill-in: clicking a row opens a side drawer (Radix Dialog with side="right") rendering `CapitalCallDetail.tsx` — fetches `/capital-calls/{id}`, lists items with per-investor amount_due / amount_paid, "Record payment" inline edit, and "Send" / "Cancel" status buttons gated by current status
  - "New capital call" button → `CapitalCallCreateDialog` collects fund_id, title, description, due_date, amount, and on submit posts to `POST /capital-calls` then `POST /capital-calls/{id}/items?mode=pro-rata` to auto-allocate
  - Replace the placeholder `/calls` route in `App.tsx`

  Implementation notes:
  - `CapitalCallCreateDialog` (`frontend/src/components/capital-calls/CapitalCallCreateDialog.tsx`) uses Radix `Select` for fund picker, posts to `POST /capital-calls`, then optionally fires `POST /capital-calls/{id}/items?mode=pro-rata` (auto-allocate is on by default with a checkbox to opt out — handy when there are no approved commitments yet so we don't 400 the user). Allocation failure is surfaced as a `toast.warning` rather than blocking the create flow.
  - `CapitalCallDetail` (`frontend/src/components/capital-calls/CapitalCallDetail.tsx`) is rendered inside a Radix `Sheet` (side="right", `sm:max-w-2xl`). It fetches `/capital-calls/{id}` plus the parent fund's `/funds/{fund_id}/commitments` to map `commitment_id → investor name` for the allocation table. KPI block shows amount / paid / allocated, with a `ProgressBar` keyed off `paidTotal / amount` and `tone="brass"` when overdue.
  - Send is enabled only for `draft`/`scheduled` (and gated on having items); Cancel is enabled for any non-final status. Per-row "Record payment" is an inline numeric input + Save button that PATCHes `/capital-calls/{call_id}/items/{item_id}` with `amount_paid` plus today's `paid_at`. After each successful mutation we invalidate `["/capital-calls"]`, the keyed call detail, the parent fund's `/funds/{fund_id}/capital-calls`, `/funds/{fund_id}`, `/funds/{fund_id}/overview`, and `["/dashboard"]` so KPI strips refresh.
  - Page-level KPI strip computes from a separate unfiltered `useApiQuery("/capital-calls")` so the overview totals stay stable as the user filters; the visible table reflects the filtered query result.

- [x] Port the Distributions page:
  - Create `frontend/src/pages/DistributionsPage.tsx` mirroring the Capital Calls page exactly (list, filters, drawer detail, create dialog, send/cancel actions) but pointing at `/distributions` endpoints
  - Replace the placeholder `/distributions` route in `App.tsx`

  Implementation notes:
  - `DistributionCreateDialog` (`frontend/src/components/distributions/DistributionCreateDialog.tsx`) mirrors `CapitalCallCreateDialog` — fund picker, title, amount, `distribution_date` (required) and optional `record_date`, description. Auto-allocate checkbox fires `POST /distributions/{id}/items?mode=pro-rata` after the create POST. Allocation failure is surfaced as a `toast.warning` (e.g. fund has no approved commitments yet) so the create still succeeds. Invalidates `["/distributions"]`, the parent fund's `/funds/{fund_id}/distributions`, `/funds/{fund_id}`, `/funds/{fund_id}/overview`, and `["/dashboard"]`.
  - `DistributionDetail` (`frontend/src/components/distributions/DistributionDetail.tsx`) is rendered inside the same Radix `Sheet` skeleton (`side="right"`, `sm:max-w-2xl`). Header shows "Distributed {distribution_date}" plus optional "Record {record_date}". KPI block shows amount / paid / allocated with a brand-tone progress bar (no `overdue` status on distributions). Send is gated to `draft|scheduled` and requires items > 0; Cancel is enabled for any non-final status. Per-row "Record payment" PATCHes `/distributions/{distribution_id}/items/{item_id}` with `amount_paid` + today's `paid_at` and invalidates the same query scopes.
  - `DistributionsPage` reuses the CapitalCalls KPI/filter/table layout: 4-stat KPI strip (Open / Events / Lifetime distributed / Lifetime paid), Radix `Select` filters for `fund_id` and `status`, a separate unfiltered query feeds the KPI summary so totals stay stable as the user filters. Clicking a row opens the drawer; "New distribution" button opens the create dialog and auto-selects the freshly created row.
  - `App.tsx` now routes `/distributions` to `DistributionsPage` (replacing the `ComingSoon` placeholder).

- [x] Surface relevant counts in the Topbar:
  - The Topbar's notifications bell shows `unread_notifications_count` from `GET /notifications` (or the dashboard overview), with a small brass badge when > 0
  - Click navigates to `/notifications`

  Implementation notes:
  - `Topbar.tsx` now reads `unread_notifications_count` from `useApiQuery("/dashboard/overview")` (with `staleTime: 60_000`) instead of polling `/notifications` with `limit: 1`. The dashboard endpoint already returns a true integer count, so no client-side `.length` capped at the page size.
  - The previous bare brass dot is replaced with a numeric badge: a `bg-brass-500` rounded pill at `-right-0.5 -top-0.5` showing the count (capped to "99+" for ≥ 100). The badge is only rendered when `unreadCount > 0`, preserving the "no decoration when zero" behaviour. `aria-label` on the bell link surfaces the count to screen readers (e.g. "Notifications (3 unread)").
  - Click target is unchanged — `<Link to="/notifications">` already navigated to the notifications route (currently a `ComingSoon` placeholder; the page will be ported in a later phase).

- [x] Optimistic-invalidation pattern (use this same approach in all three pages):
  - On any successful mutation (create / patch / send / cancel / record-payment), call `queryClient.invalidateQueries({ queryKey: [primary] })` AND any nested keys (`["funds", fundId]`, `["dashboard"]`) so KPI strips refresh
  - Show a `sonner` toast confirming the action

  Implementation notes:
  - Audited all mutations across the three pages. The shared shape is: a small `invalidate*Scopes()` helper that hits the primary list query (`["/investors"]` / `["/capital-calls"]` / `["/distributions"]`), the keyed detail query when relevant, the parent fund's nested keys (`/funds/{fund_id}`, `/funds/{fund_id}/overview`, plus the matching `/funds/{fund_id}/capital-calls` or `/funds/{fund_id}/distributions`), and `["/dashboard"]`. `onSuccess` callbacks fire a `sonner` toast first and then call the helper.
  - `CapitalCallDetail.invalidateCallScopes()` and `DistributionDetail.invalidateDistributionScopes()` already covered send / cancel / record-payment. `CapitalCallCreateDialog` and `DistributionCreateDialog` already invalidated the same set after the create + pro-rata flow. `InvestorCreateDialog` already invalidated `["/investors"]` + `["/dashboard"]`.
  - The only inconsistency was in `InvestorDetailPanel`: `updateContact` (toggle primary) and `createContact` invalidated only the contacts subquery and skipped the parent investor + dashboard. Refactored both to share a new `invalidateInvestorScopes()` helper that hits the contacts list, the keyed `[/investors/{investor_id}]` query, the master `["/investors"]` list, and `["/dashboard"]` so the pattern is uniform across all five mutating components. Toast call moved to fire before invalidation (matches the order used in CapitalCallDetail / DistributionDetail).
  - `pnpm run lint` (tsc --noEmit) passes after the change.

- [x] Type-check + visual smoke test:
  - `pnpm run lint` from `frontend/`
  - In the browser, walk through: create investor → create commitment from FundDetail → create a capital call with pro-rata allocation → record a payment → confirm the parent call flips to `partially_paid` and the FundDetail KPI strip updates

  Implementation notes:
  - `pnpm run lint` (tsc --noEmit) passes cleanly with no errors.
  - Static verification of the smoke-test path: `InvestorsPage`, `CapitalCallsPage`, `DistributionsPage`, and all their dialogs/detail components are in place; the `/investors`, `/calls`, `/distributions` routes in `App.tsx` resolve to the real pages (not `ComingSoon`).
  - `CapitalCallDetail.invalidateCallScopes()` covers the full chain needed for the FundDetail KPI strip refresh after a recorded payment: `["/capital-calls"]`, the keyed `[/capital-calls/{call_id}]`, the parent fund's `[/funds/{fund_id}/capital-calls]`, `[/funds/{fund_id}]`, `[/funds/{fund_id}/overview]`, and `["/dashboard"]` — so the parent fund pane re-fetches when the user navigates back.
  - The "parent call flips to `partially_paid` after a partial payment" assertion is locked in by backend tests `test_capital_calls_api.py:211` and `:299`, so the server-side state transition is regression-safe even without the manual click-through.
  - The interactive browser walkthrough itself was not executed by this agent run: auth uses real Hanko-issued JWTs (`backend/app/core/auth.py`) with no dev bypass, so an automated browser session can't get past the `/login` screen. Recommend the human run the walkthrough locally before shipping the phase.

- [x] Run repo gates: `make lint`, `make test`

  Implementation notes:
  - `make lint` passes cleanly: import smoke test, `ruff check --fix`, `ty check`, `black`, and `isort` all report no issues (86 files unchanged, 3 skipped — alembic/tests/.venv).
  - `make test` passes: **144 passed in 5.28s**. No existing test was disturbed by Phase 07 (frontend-only changes).
  - `make openapi` was not re-run because no backend routes / schemas were modified in this phase; `backend/openapi.json` and `frontend/src/lib/schema.d.ts` are still in sync from the prior phase.
