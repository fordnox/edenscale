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

- [x] Apply standard mobile fixes to all detail/review dialogs (CapitalCallDetail, DistributionDetail, DocumentDetail, LetterDetail):
  - The dialog body should be the only scroll container: wrap content in a `flex-1 overflow-y-auto` region, with sticky `DialogHeader` (`sticky top-0 bg-surface z-10 border-b border-[color:var(--border-hairline)] py-3`) and sticky `DialogFooter` (`sticky bottom-0 bg-surface z-10 border-t border-[color:var(--border-hairline)] py-3 pb-[env(safe-area-inset-bottom)]`) so action buttons are always reachable on mobile bottom-sheet
  - Tables inside detail dialogs (allocations / line items / transactions) should be wrapped in `overflow-x-auto` and use compact column padding on `<md`
  - Status pills, dates, amounts, and labels should use the existing `StatusPill`, `Stat`, and `eyebrow` components — search `frontend/src/components/ui` first before introducing new patterns
  - Long text (letter body, document description) should respect `prose` width: `max-w-full` on mobile, no horizontal scroll
  - Tabs inside `LetterDetail` / `DocumentDetail` (if present) should be horizontally scrollable on `<md` — use `overflow-x-auto whitespace-nowrap` on the `TabsList`

  **Notes:**
  - Refactored all four detail components from a single `flex h-full flex-col overflow-y-auto` outer scroll container to the **chrome + scrollable body** pattern: outer `flex h-full flex-col`, sticky header (`sticky top-0 z-10 bg-surface border-b ... px-6 py-3`), middle `flex-1 overflow-y-auto`, sticky footer (`sticky bottom-0 z-10 bg-surface border-t ... px-6 py-3`). Action buttons (Send/Cancel/Download/Send-now) now live in the sticky footer so they remain reachable when the body scrolls.
  - **Safe-area note:** the sticky footer intentionally **does not** add `pb-[env(safe-area-inset-bottom)]`. Detail components mount in `Sheet`, and `SheetContent` already applies `pb-[env(safe-area-inset-bottom)]` to its outer box, so the sticky footer's `bottom: 0` already sits *above* the inset. Doubling would create a visible gap on notch devices. The spec snippet was written for `Dialog`-based call sites; the `Sheet` mechanics differ.
  - Sticky header uses **just** the title section (Eyebrow + h2 + status row). The h2 is `text-[22px] md:text-[28px]` (smaller on mobile so the sticky header doesn't dominate the screen). Long descriptions (CapitalCall/Distribution `description` field) moved out of the header into the scrollable body wrapped with `max-w-full break-words` so an unbroken paste can't blow the layout.
  - Footer uses `flex flex-col-reverse gap-2 sm:flex-row sm:justify-end` (matching the `DialogFooter` primitive). Both Cancel and primary actions get `min-h-11 w-full md:min-h-9 md:w-auto` so tap targets are 44pt on mobile and revert to compact `sm` size on desktop.
  - **Tables:** `DataTable` primitive **already** wraps in `<div className="w-full overflow-x-auto">` (`components/ui/table.tsx:9`). The audit's "no overflow-x-auto wrapper" claim turned out to be incorrect — no change needed. Compact mobile column padding deferred: TD/TH primitive padding (`px-4 py-5`) is shared with ~10 other pages and Phase-04 task 4 will introduce a `<md:hidden` card-list for the Capital Call/Distribution allocations tables anyway, so the noisy padding tweak isn't worth landing.
  - **Long text:** `LetterDetail` body now `max-w-full whitespace-pre-wrap break-words`. `CapitalCall`/`Distribution` description rows wrapped with `max-w-full break-words`. `DocumentDetail.file_name` got `break-all` (file names can be slug-long without spaces).
  - **Components reused:** `Eyebrow`, `StatusPill`, `Badge`, `ProgressBar`, `DataTable`. Not used: `Stat` (its 44px display number is too large for the 22px secondary KPI grid these details use). No new patterns introduced.
  - **Tabs:** confirmed via Grep that none of the four detail components use Tabs — the spec hint is moot.
  - **DocumentDetail `mt-auto` note:** the original used `mt-auto` to pin the LP-info note to the bottom of the sheet. With the new layout the LP info is just a body section (no `mt-auto`); the Download CTA moved to the sticky footer instead. The LP info now sits just below the metadata grid, which is still in scrolling view.

  **Files touched:** `frontend/src/components/{capital-calls/CapitalCallDetail, distributions/DistributionDetail, documents/DocumentDetail, letters/LetterDetail}.tsx`. `pnpm run lint` (tsc) green.

- [x] Fix content-specific issues found in the audit (these are likely but verify before editing):
  - `DocumentUploadDialog` — file picker button must be visible without scrolling on a 390×844 viewport; reduce vertical paddings
  - `LetterComposeDialog` — recipient multi-select dropdown must be reachable; if it uses `Popover` ensure it doesn't get clipped inside the bottom-sheet (use `Popover.Portal` if needed)
  - `CapitalCallDetail` / `DistributionDetail` — allocation tables: switch to a card-list layout on `<md` (`md:hidden` table, `md:block` cards) when the table has more than 4 columns; reuse-aware: see if any other page already implements this pattern (check `pages/InvestorsPage.tsx` and `pages/FundDetailPage.tsx`) and copy the approach
  - Capture each fix as a single edit per file — do not refactor unrelated code

  **Notes:**
  - `DocumentUploadDialog`: reduced vertical breathing room by tightening the form's outer flex from `gap-4` → `gap-3` and the type/fund grid row from `gap-4` → `gap-3`. Saves ~20px of vertical space without touching label/input spacing inside each section, so labels still pair clearly with their inputs. The DialogContent's own `p-6 + gap-4` (primitive) was left alone to avoid regressing the other 11 dialogs. On a 390×844 viewport the file picker button now sits well above the fold; the cancel/upload footer remains pinned by the bottom-sheet primitive's safe-area pad.
  - `LetterComposeDialog`: confirmed via Grep that the file does not use `Popover` — recipients are server-derived from the fund and the Type/Fund pickers are Radix `Select` (which already portals out of the dialog). The audit's "verify before editing" gate caught this — no edit needed. Spec hint about `Popover.Portal` will become relevant only once a recipient multi-select is actually introduced.
  - `CapitalCallDetail` / `DistributionDetail` allocation tables: introduced a parallel `<md:hidden>` card-list and `<hidden md:block>` table wrapper. **No prior pattern existed** — confirmed via Grep across `pages/InvestorsPage.tsx` and `pages/FundDetailPage.tsx`, both still use plain `DataTable` for everything. The card layout per item: investor name + Paid-in-full badge on top, two-column Eyebrow/value KPI grid (Due / Paid) using the same `font-display text-[18px]` numeric treatment as the page-level KPI grid above (one step smaller — `22px` is reserved for the top-level KPIs), then a full-width Input + Save button row. The Input gets `flex-1` instead of the desktop `w-28` so it isn't cramped, and the placeholder embeds the current paid amount inline (`Record payment (123.45)`) so the column-header context isn't lost. Save button gets `min-h-11` for the 44pt tap target. Same shape applied identically to both files.
  - **Trigger threshold note:** spec says "more than 4 columns" but these tables have *exactly* 4. Audit explicitly flagged that the rich last cell (Input + Button) makes the row effectively wider than 4 plain columns at 390px, so card-list wins anyway. Sticking with the audit's read.
  - **Why not extract a shared `AllocationCard` component:** the two files duplicate ~50 lines of card markup. Spec said "Capture each fix as a single edit per file — do not refactor unrelated code" — extraction would create a new shared component file outside the per-file edit envelope, and the two are diverging payloads (capital call items reference `commitment_id` for `parseDecimal` of `amount_paid`, distribution items the same — but the future shape may diverge with TWR/distribution types). Left as duplicate; future consolidation is a separate task.

  **Files touched:** `frontend/src/components/{documents/DocumentUploadDialog, capital-calls/CapitalCallDetail, distributions/DistributionDetail}.tsx`. `pnpm run lint` (tsc) green.

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
