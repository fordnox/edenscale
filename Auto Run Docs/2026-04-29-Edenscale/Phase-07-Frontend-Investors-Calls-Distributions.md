# Phase 07: Frontend — Investors, Capital Calls, Distributions

This phase ports the LP- and capital-flow-focused pages from the prototype: Investors (list + detail panel), Capital Calls (list + drill-in), and Distributions (list + drill-in). All pages call the API via the generated client and use TanStack Query mutations for create / update / send / cancel actions, with optimistic invalidation on success.

## Tasks

- [ ] Read the prototype pages we're porting before writing new code:
  - `edenscale/src/pages/InvestorsPage.tsx`, `edenscale/src/pages/CapitalCallsPage.tsx`, `edenscale/src/pages/DistributionsPage.tsx`
  - The shared `frontend/src/components/ui/StatusPill.tsx` from Phase 06 — reuse it instead of re-implementing color logic
  - The shared `useApiQuery` / `useApiMutation` hooks from Phase 06

- [ ] Port the Investors page:
  - Create `frontend/src/pages/InvestorsPage.tsx`. Master/detail layout: list on the left with `useApiQuery("/investors")`, detail panel on the right showing the selected investor's contacts, commitments, and recent activity
  - Master list columns: name, investor_type, accredited badge, total_committed (numeric tabular), fund_count
  - Detail panel tabs: Contacts, Commitments. Contacts tab shows a table with primary star icon and an "Add contact" form. Commitments tab shows the investor's commitment table with links to each fund
  - "New investor" button → `InvestorCreateDialog` posting to `POST /investors`
  - Inline edit primary contact via `PATCH /investors/{id}/contacts/{contactId}` and toggle is_primary
  - Replace the placeholder `/investors` route in `App.tsx`

- [ ] Port the Capital Calls page:
  - Create `frontend/src/pages/CapitalCallsPage.tsx` listing all calls via `useApiQuery("/capital-calls")` with filters `?fund_id`, `?status` exposed as Radix Select dropdowns. Table columns: fund, title, due_date, amount, status pill, paid % progress bar
  - Drill-in: clicking a row opens a side drawer (Radix Dialog with side="right") rendering `CapitalCallDetail.tsx` — fetches `/capital-calls/{id}`, lists items with per-investor amount_due / amount_paid, "Record payment" inline edit, and "Send" / "Cancel" status buttons gated by current status
  - "New capital call" button → `CapitalCallCreateDialog` collects fund_id, title, description, due_date, amount, and on submit posts to `POST /capital-calls` then `POST /capital-calls/{id}/items?mode=pro-rata` to auto-allocate
  - Replace the placeholder `/calls` route in `App.tsx`

- [ ] Port the Distributions page:
  - Create `frontend/src/pages/DistributionsPage.tsx` mirroring the Capital Calls page exactly (list, filters, drawer detail, create dialog, send/cancel actions) but pointing at `/distributions` endpoints
  - Replace the placeholder `/distributions` route in `App.tsx`

- [ ] Surface relevant counts in the Topbar:
  - The Topbar's notifications bell shows `unread_notifications_count` from `GET /notifications` (or the dashboard overview), with a small brass badge when > 0
  - Click navigates to `/notifications`

- [ ] Optimistic-invalidation pattern (use this same approach in all three pages):
  - On any successful mutation (create / patch / send / cancel / record-payment), call `queryClient.invalidateQueries({ queryKey: [primary] })` AND any nested keys (`["funds", fundId]`, `["dashboard"]`) so KPI strips refresh
  - Show a `sonner` toast confirming the action

- [ ] Type-check + visual smoke test:
  - `pnpm run lint` from `frontend/`
  - In the browser, walk through: create investor → create commitment from FundDetail → create a capital call with pro-rata allocation → record a payment → confirm the parent call flips to `partially_paid` and the FundDetail KPI strip updates

- [ ] Run repo gates: `make lint`, `make test`
