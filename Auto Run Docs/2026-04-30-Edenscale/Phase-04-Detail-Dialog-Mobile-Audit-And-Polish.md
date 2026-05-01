# Phase 04: Detail Dialog Mobile Audit + Final Polish

Phase 01 fixed dialog primitives (background, tokens, bottom-sheet on mobile) so every dialog inherited a baseline. This phase walks each individual dialog/detail/compose component on real mobile widths and fixes content-level issues that the primitive fix can't solve: cramped headers, side-by-side form rows that should stack, tables that overflow, file dropzones with tiny tap targets, and footers where action buttons get hidden by the keyboard. Scope is the chrome-adjacent dialogs the user already uses — no new features, no visual refresh. After this phase the mobile experience is shippable end-to-end.

## Tasks

- [x] Inventory every dialog/detail call site and confirm each one already opens correctly post-Phase-01:
  - List of files to audit:
    - `frontend/src/components/capital-calls/CapitalCallCreateDialog.tsx`
    - `frontend/src/components/capital-calls/CapitalCallDetail.tsx`
    - `frontend/src/components/distributions/DistributionCreateDialog.tsx`
    - `frontend/src/components/distributions/DistributionDetail.tsx`
    - `frontend/src/components/documents/DocumentDetail.tsx`
    - `frontend/src/components/documents/DocumentUploadDialog.tsx`
    - `frontend/src/components/letters/LetterComposeDialog.tsx`
    - `frontend/src/components/letters/LetterDetail.tsx`
    - `frontend/src/components/funds/FundCreateDialog.tsx`
    - `frontend/src/components/funds/FundEditDialog.tsx`
    - `frontend/src/components/investors/InvestorCreateDialog.tsx`
    - `frontend/src/components/tasks/TaskCreateDialog.tsx`
  - For each: open at 390×844 (iPhone 14) and 768×1024 (iPad) widths and capture issues in a scratch list at `Auto Run Docs/2026-04-30-Edenscale/Working/phase-04-audit.md` with one section per file (front matter optional — this is internal scratch, not a published doc)

- [x] Apply standard mobile fixes to all create/compose dialogs (Capital Call, Distribution, Document Upload, Letter Compose, Fund Create, Fund Edit, Investor Create, Task Create):
  - Form rows that use `grid grid-cols-2` for label/input pairs should switch to `grid-cols-1 md:grid-cols-2`
  - Inputs/selects/textareas should have `text-base md:text-sm` so iOS does not zoom on focus (16px floor)
  - Footers (`DialogFooter`) should be `flex-col-reverse gap-2 md:flex-row md:justify-end` (the primitive default is already close to this — verify each call site doesn't override)
  - Primary action buttons get `min-h-11 md:min-h-9` for tap targets; full-width on mobile (`w-full md:w-auto`)
  - Add `pb-[env(safe-area-inset-bottom)]` to the dialog content's inner footer wrapper so iOS home-indicator does not overlap the action button
  - File dropzones (DocumentUploadDialog) should expose a large button-style "Choose file" trigger as well as the dropzone surface — the dropzone itself becomes a hint on mobile (`hidden md:block`) since drag-and-drop doesn't apply

  **Notes:**
  - Grid pair rows already used `grid-cols-1 md:grid-cols-2` everywhere; nothing to change.
  - Input/Textarea primitives already include the `text-base md:text-sm` 16px floor. The two **native `<select>`** holdouts in `FundCreateDialog`/`FundEditDialog` were swapped to the Radix `Select` (`SelectTrigger`/`SelectContent`/`SelectItem`) — same pattern every other dialog already uses. This eliminates iOS focus zoom and gives keyboard/portal behavior consistent with the rest of the app.
  - `DialogFooter` primitive uses `sm:flex-row sm:justify-end` (640px breakpoint) instead of the spec's `md:` (768px). The audit explicitly accepted this delta — no call site overrides the primitive, so left as-is.
  - Added `min-h-11 md:min-h-9` to **both** Cancel and primary action buttons in all 8 dialogs (Cancel for tap-target consistency since it lives in the stacked-reverse mobile column). Primary additionally gets `w-full md:w-auto` per spec. `LetterComposeDialog` has 3 buttons (Cancel / Save draft / Send now) — Send now is the primary; the other two get tap target only.
  - Added `className="pb-[env(safe-area-inset-bottom)]"` to every `DialogFooter`. Redundant with the bottom-sheet primitive's `max-md:pb-[calc(env(safe-area-inset-bottom)+1.5rem)]` but per spec for explicit declaration.
  - `DocumentUploadDialog` file picker: replaced the bare `<Input type="file">` with a hidden `<input type="file" className="sr-only">` driven by a `useRef<HTMLInputElement>` + button `onClick={() => fileInputRef.current?.click()}`. Button is `min-h-11 w-full md:min-h-9 md:w-auto`, shows the chosen file name with truncation and an MB readout below. Audit explicitly noted no dropzone exists today, so the spec's "hide the dropzone on mobile" half is a no-op — left alone.

  **Files touched:** `frontend/src/components/{capital-calls/CapitalCallCreateDialog, distributions/DistributionCreateDialog, documents/DocumentUploadDialog, letters/LetterComposeDialog, funds/FundCreateDialog, funds/FundEditDialog, investors/InvestorCreateDialog, tasks/TaskCreateDialog}.tsx`. `pnpm run lint` (tsc) green.

- [ ] Apply standard mobile fixes to all detail/review dialogs (CapitalCallDetail, DistributionDetail, DocumentDetail, LetterDetail):
  - The dialog body should be the only scroll container: wrap content in a `flex-1 overflow-y-auto` region, with sticky `DialogHeader` (`sticky top-0 bg-surface z-10 border-b border-[color:var(--border-hairline)] py-3`) and sticky `DialogFooter` (`sticky bottom-0 bg-surface z-10 border-t border-[color:var(--border-hairline)] py-3 pb-[env(safe-area-inset-bottom)]`) so action buttons are always reachable on mobile bottom-sheet
  - Tables inside detail dialogs (allocations / line items / transactions) should be wrapped in `overflow-x-auto` and use compact column padding on `<md`
  - Status pills, dates, amounts, and labels should use the existing `StatusPill`, `Stat`, and `eyebrow` components — search `frontend/src/components/ui` first before introducing new patterns
  - Long text (letter body, document description) should respect `prose` width: `max-w-full` on mobile, no horizontal scroll
  - Tabs inside `LetterDetail` / `DocumentDetail` (if present) should be horizontally scrollable on `<md` — use `overflow-x-auto whitespace-nowrap` on the `TabsList`

- [ ] Fix content-specific issues found in the audit (these are likely but verify before editing):
  - `DocumentUploadDialog` — file picker button must be visible without scrolling on a 390×844 viewport; reduce vertical paddings
  - `LetterComposeDialog` — recipient multi-select dropdown must be reachable; if it uses `Popover` ensure it doesn't get clipped inside the bottom-sheet (use `Popover.Portal` if needed)
  - `CapitalCallDetail` / `DistributionDetail` — allocation tables: switch to a card-list layout on `<md` (`md:hidden` table, `md:block` cards) when the table has more than 4 columns; reuse-aware: see if any other page already implements this pattern (check `pages/InvestorsPage.tsx` and `pages/FundDetailPage.tsx`) and copy the approach
  - Capture each fix as a single edit per file — do not refactor unrelated code

- [ ] Final QA pass on the full chrome and dialogs:
  - Spin up `make start-frontend` and `make start-backend`; seed demo data via `make seed` if needed (idempotent per Phase 09 work)
  - Walk every authenticated page on mobile width: Dashboard, Funds (list + detail), Investors, Capital Calls, Distributions, Documents, Letters, Tasks, Notifications, Profile, Audit Log, Organization Settings
  - For each dialog, verify: opens as bottom-sheet, content readable, header sticky, footer sticky with safe-area padding, no horizontal scroll on body, primary action visible without keyboard interference, ⌘K palette still opens over the dialog cleanly
  - Walk same flows on desktop ≥1280px width: dialogs are centered modals, sidebar visible inline, ⌘K from Topbar works, user-menu at bottom-left of sidebar opens upward

- [ ] Run all quality gates and clean up:
  - `make test` (backend) — should be untouched but confirm green
  - `make lint` (backend)
  - `cd frontend && pnpm run lint` (tsc)
  - `make openapi` only if any backend route signatures changed (none expected this phase)
  - Delete `Auto Run Docs/2026-04-30-Edenscale/Working/phase-04-audit.md` scratch file once fixes are merged in — it has served its purpose
