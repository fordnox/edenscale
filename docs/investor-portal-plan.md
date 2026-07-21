# Investor portal — feature plan (fundrbird gap analysis)

> **Reconciled against code 2026-07-21** (plan 010). The gap table below and
> "central dependency" section originally described a pre-Phase-2 state (no
> valuation model). Phase 2 shipped `FundValuation` / NAV / TVPI / RVPI
> (see `apps/backend/app/models/fund_valuation.py`,
> `apps/backend/app/services/metrics.py`) and the "Status" section at the
> bottom of this document already said so — but the gap table and the
> "central dependency" section had not been updated to match. Both are
> corrected below. Phases 3–5 were re-checked against the code and are
> still not built (verified: no `PortfolioCompany`, `PortfolioInvestment`,
> or `ReportPeriod` models exist under `apps/backend/app/models/`).

Reference: fundrbird's Contrarian Ventures LP portal. This maps its functionality
to edenscale's `apps/investor` and lays out a phased plan. Structure/feature
notes only — no competitor content is reproduced.

## What fundrbird's portal is

A per-investor LP portal (reached via a tokenized `/investor/<uuid>` link, no
login) with three layers:

1. **Portal home** — a consolidated position table (row per fund + Total:
   Commitment, Paid-in, Distributed, Unfunded, Capital Account at Fair Value
   (NAV), Fund Multiple (TVPI), Fund Net IRR), a welcome block, and an
   **updates feed** (capital notices + investor reports, chronological, with
   amount / PAID status / Details, plus "Go to archive").
2. **Per-fund investor report** — a full structured quarterly report with a
   table of contents, VIEW/DOWNLOAD (PDF), and a report-period selector.
   Sections: Fund overview (terms), Executive summary (rich narrative + charts),
   Fund performance status (NAV, Gross/Net IRR, TVPI, DPI, RVPI, PICC),
   Portfolio summary (per-company cost/fair value/MOIC/IRR), Portfolio asset
   details, **Individual capital account** (the LP's own statement — their
   commitment, paid-in, capital account at fair value, per-investment schedule),
   GP fees / carried interest / fund opex, Cash flows & Net IRR, Fund financial
   statements (balance sheet + income statement), Downloads (attached PDFs).
3. **Archive** — past reports and notices.

## Where edenscale stands

| fundrbird feature | edenscale `apps/investor` |
|---|---|
| Consolidated position table + Total | **DONE** (DashboardPage) |
| Updates feed (unified timeline) | **DONE** (UpdatesFeed on DashboardPage) |
| Top-bar navigation (no sidebar) | **DONE** (TopNav) |
| DPI / IRR from cashflows | DONE (fund overview, dashboard) |
| Capital calls / distributions / documents / letters / notifications | DONE (LP-scoped pages) |
| Profile | DONE |
| **NAV / Fair Value, TVPI, RVPI** | **DONE** — `FundValuation` model + `metrics.fund_metrics` (`nav`, `tvpi`, `rvpi`); investor position table shows Fair Value + TVPI, fund detail shows fund-wide NAV/TVPI/RVPI |
| **Portfolio (deal-level) data** | **MISSING** — no portfolio-company domain (Phase 3, not started) |
| **Structured quarterly report + PDF** | **MISSING** (Phase 4, not started) |
| **Individual capital-account statement** | **MISSING** (Phase 5, not started; needs Phase 3 portfolio data, not just NAV — NAV is done) |
| Report archive | Partial (Documents page lists report-type docs) |
| Tokenized no-login share link | Different model (Hanko per-user auth) |

## The central dependency

Everything fundrbird shows above the DPI/IRR line — Fair Value, TVPI, RVPI,
the capital-account statement, portfolio marks — depends on a **valuation / NAV
model**. **That foundation has been built** (Phase 2, complete): managers
record fund NAV marks (`FundValuation`), and `nav` / `tvpi` / `rvpi` flow
through `app/services/metrics.py` to both the manager and investor apps. The
remaining fundrbird-parity gaps (portfolio/deal-level data, the structured
quarterly report + PDF, the individual capital-account statement) are
downstream of this foundation and are now unblocked, not blocked on it. The
phases below were originally ordered around getting past this fork; Phases
3–5 are what's left.

## Phased plan

### Phase 0 — Portal UX parity (DONE this session)
- Consolidated position table with Total row.
- Unified updates feed (capital notices + distributions + letters).
- Top-bar navigation, sidebar removed.

### Phase 1 — Reports & notices surfacing — DONE
- **Reports page** (`/investor/:orgSlug/reports`, new "Reports" nav item):
  report-type documents grouped by fund, latest highlighted with VIEW/DOWNLOAD
  (presigned), older ones listed (`ReportsPage.tsx`).
- **Archive page** (`/investor/:orgSlug/archive`): the full activity timeline
  (`UpdatesFeed` at high limit), reached via a "Go to archive" link on the
  dashboard feed (`ArchivePage.tsx`).
- **Notice detail sheet** (`NoticeDetailSheet.tsx`): capital-call and
  distribution rows are now clickable → a sheet with the LP's amount due/paid,
  key dates, description, and their allocation-item breakdown.
- Investor typecheck + build; gateway build green. Phase 1 complete.

### Phase 2 — Valuation / NAV foundation — approved & IN PROGRESS
The no-NAV decision was reversed by the user; NAV/TVPI/RVPI are being reintroduced.

**Backend — DONE:**
- `FundValuation` model (fund-level NAV per `as_of_date`, one mark per date) +
  migration `b2c3d4e5f6a7`.
- `FundValuationRepository` (upsert-by-date, list, delete).
- `metrics.fund_metrics` now returns `nav` (latest mark), `tvpi =
  (distributed + nav)/called`, `rvpi = nav/called` (None until marked); DPI/IRR
  unchanged. Helpers `latest_fund_nav` / `latest_fund_navs`.
- Endpoints under `/funds/{id}/valuations`: GET (any member who can view the
  fund, incl. LPs), POST (upsert) + DELETE (managers only).
- `FundOverview` gains `nav/tvpi/rvpi`; `FundListItem`/`FundRead` gain `nav`.
- Tests (`test_fund_valuations.py`), lint, OpenAPI client regenerated.
  NOTE: `make openapi`'s turbo `generate-client` step doesn't treat
  `openapi.json` as an input — force with
  `pnpm --filter @edenscale/api run generate-client` after backend API changes.

**Frontend — DONE:**
- Investor position table now has **Fair Value** (LP NAV = ownership × fund NAV)
  and **TVPI** columns + Fair Value in the Total row; fund detail shows the LP's
  own fair value/TVPI and the fund-wide NAV/TVPI/RVPI.
- Manager fund overview: TVPI + Fund NAV metric cells, plus a **Fund NAV history**
  card (`FundValuationsCard`) to record (date + NAV), list, and delete marks.
- Both apps typecheck + build; gateway build green.

Phase 2 complete.

### Phase 3 — Portfolio (deal-level) domain
- New models: `PortfolioCompany` (name, geography, industry, first-investment
  date), `PortfolioInvestment` (cost, fair value, MOIC, ownership, per fund).
- Manager UI to manage holdings + marks; investor read-only **Portfolio
  summary** + **Portfolio asset details** pages/sections.
- Effort: large, ~2–3 weeks. Depends on Phase 2 for fair-value marks.

### Phase 4 — Structured quarterly report + PDF
- `ReportPeriod` (fund + quarter/as-of) tying together the computed sections
  (performance status, cash flows, portfolio) + authored narrative
  (rich-text **Executive summary**) + attached PDFs.
- Investor **report viewer** (ToC, sections, period selector) and **PDF export**
  (server-side render of the same content).
- Effort: large, ~2–4 weeks. Depends on Phases 2–3.

### Phase 5 — Individual capital-account statement
- The LP's own statement derived from their commitment + NAV allocation:
  commitment overview, capital account roll-forward, per-investment schedule
  (their pro-rata of each holding), other payments.
- Effort: medium, ~1 week. Depends on Phases 2–3.

### Optional — Tokenized share-link access
- fundrbird uses a no-login per-investor URL. edenscale uses Hanko. If desired,
  add signed magic-link tokens that resolve to an LP membership (read-only),
  as an alternative entry path. Security-sensitive; scope carefully.

## Status

- **Phases 0, 1, 2: DONE.** The portal now has the consolidated position table
  (with Fair Value + TVPI), the unified updates feed + archive, a reports
  center, notice detail sheets, a top-bar nav, and a full NAV/valuation
  foundation (managers mark fund NAV → TVPI/RVPI/fair value flow to LPs).
- **Phases 3–5: remaining.** These are the deep quarterly-report build:
  portfolio (deal-level) domain, the structured report viewer + PDF export, and
  the individual capital-account statement. They depend on the Phase 2 NAV
  foundation (now in place) and are large; tackle when full quarterly LP
  reporting (vs. the current portal + fair-value view) becomes the priority.
