# Phase 04 — Mobile Audit Scratch

Static review against the criteria in Phase-04. Two viewports walked: **390×844 (iPhone 14)** and **768×1024 (iPad)**. Tailwind's `md:` breakpoint is `≥768px`, so the iPad sits *at* the desktop side of every `md:`-gated rule — i.e. iPad behaves like desktop for forms but still narrower than a centered modal's `sm:max-w-xl`.

## Baseline already inherited from Phase 01

- `DialogContent` (`components/ui/dialog.tsx`): bottom-sheet under `md` (`max-md:bottom-0 max-md:max-h-[92svh] max-md:overflow-y-auto max-md:rounded-t-lg max-md:pb-[calc(env(safe-area-inset-bottom)+1.5rem)]`); centered modal at `sm:max-w-lg` upward.
- `DialogFooter`: `flex flex-col-reverse gap-2 sm:flex-row sm:justify-end` — already stacks on mobile. **Note:** uses `sm:`, not `md:`, so it switches to row at 640px (small phones in landscape, all iPad). Phase-04 spec says `md:flex-row` — there is a small range (640–767px) where the spec wants stacked but the primitive gives row. Acceptable; do not regress the call sites.
- `Input` and `Textarea` already include `text-base md:text-sm` baseline (no iOS zoom). Native `<select>` in `FundCreateDialog`/`FundEditDialog` does NOT inherit this — see per-file notes.
- Detail components (`*Detail.tsx`) are mounted in `Sheet` (`pages/*Page.tsx`), **not** `Dialog`. The Sheet primitive uses `w-full sm:max-w-sm md:w-3/4` and renders right-side. Mobile = full width slide-from-right. The Phase-04 spec mentions `bottom-sheet` for detail; the *Sheet primitive* is right-side, not bottom. The detail components themselves wrap in `flex h-full flex-col overflow-y-auto` so the entire body scrolls as one container — header is **not** sticky on mobile, footer/action bar is **not** sticky.
- No existing card-list-on-mobile pattern in `InvestorsPage.tsx` / `FundDetailPage.tsx` — Phase-04 task 4 will need to introduce one.

## Per-file findings

### `components/capital-calls/CapitalCallCreateDialog.tsx`

- `DialogContent` is `sm:max-w-xl` — opens as bottom-sheet on iPhone, centered ~36rem modal on iPad+. OK.
- Form rows already use `grid-cols-1 gap-4 md:grid-cols-2` for amount/due-date pair. ✓
- Inputs and Textarea inherit `text-base md:text-sm` from primitives. ✓
- `DialogFooter` not overridden; inherits stacked-reverse on mobile. ✓
- Buttons are `size="sm"` (h-8 ≈ 32px). **Issue:** below the 44pt minimum tap target on mobile. Spec wants `min-h-11 md:min-h-9` and `w-full md:w-auto` for primary action.
- Footer wrapper does not opt into `pb-[env(safe-area-inset-bottom)]`; bottom-sheet primitive already pads the *content* by `calc(env(safe-area-inset-bottom)+1.5rem)`. Spec asks for it on the footer wrapper too — duplicates but harmless.
- Auto-allocate row: native `<input type="checkbox" class="size-4">` (16px). Tap target small but acceptable for opt-in toggle; not flagged.

### `components/capital-calls/CapitalCallDetail.tsx`

- Mounted in `Sheet` (`pages/CapitalCallsPage.tsx:288–306`), not Dialog. Sheet is `w-full md:w-3/4` — full width on mobile.
- Outer wrapper: `flex h-full flex-col overflow-y-auto`. Single scroll container — fine, but **header (lines 153–166) and action bar (lines 196–223) are not sticky**, so on a long allocations table the user has to scroll all the way back to the top to hit Send/Cancel. Spec wants sticky header + sticky footer with safe-area padding.
- KPI grid `grid-cols-2 ... md:grid-cols-3` (line 168). Acceptable on iPhone (2 cols of compact currency); iPad gets 3 cols. ✓
- Allocations `DataTable` has 4 columns (Investor / Due / Paid / Record payment). Last column embeds an `Input` (`w-28`) + `Save` button. **Issue:** at 390px wide, this row will overflow horizontally — table has no `overflow-x-auto` wrapper. Spec wants either `overflow-x-auto` wrap or a `<md` card-list layout when columns > 4 (here exactly 4, plus the cell is rich and effectively > 4 worth of content). Recommend card-list on `<md`.
- Action buttons (`Send`/`Cancel`) are `size="sm"` — same tap-target concern as create dialogs, less critical here since they are mid-page not in a sheet footer.

### `components/distributions/DistributionCreateDialog.tsx`

- Structurally identical to `CapitalCallCreateDialog`. Same findings: small tap targets on footer buttons, otherwise OK.

### `components/distributions/DistributionDetail.tsx`

- Structurally identical to `CapitalCallDetail`. Same findings: non-sticky header/action bar, allocations table overflow risk on `<md`.

### `components/documents/DocumentDetail.tsx`

- Mounted in Sheet on `DocumentsPage`. Single `overflow-y-auto` wrapper.
- KPI grid (line 50) is `grid-cols-2` with no `md:` adjustment — fine on both viewports because content is short.
- Download button is `size="sm"` and `<Button asChild>` wrapping an `<a>`. Tap target small; spec wants `min-h-11 md:min-h-9 w-full md:w-auto`.
- No tables, no tabs, no long horizontal content. No header/footer stickiness needed since the body is short, but consistency with sibling details is desirable if applying the sticky pattern broadly.
- Footer note ("Limited partners see only…") at the bottom uses `mt-auto` — relies on the sheet content filling height. With `pb-[env(safe-area-inset-bottom)]` from the Sheet primitive, OK.

### `components/documents/DocumentUploadDialog.tsx`

- 5 form sections + checkbox + footer. At 390×844, on a bottom-sheet capped at `92svh` ≈ 776px content area, **everything fits but the file picker is at the top and the submit button is below the fold** — user must scroll. Spec wants the file picker visible without scrolling; recommends reducing vertical paddings.
- Native `<input type="file">` has the smallest possible tap target on iOS Safari. Spec wants a large button-style "Choose file" trigger plus a desktop-only dropzone hint (`hidden md:block`). **Currently there is no dropzone at all** — the input is bare. So the Phase-04 task is mostly about adding a button-style trigger; the "hide the dropzone on mobile" half is a no-op since no dropzone exists.
- Buttons are `size="sm"` again — tap-target issue.
- Two Selects in a `grid-cols-1 md:grid-cols-2` row + a third Select on its own row. Fine.

### `components/letters/LetterComposeDialog.tsx`

- `DialogContent` is `sm:max-w-2xl` (wider than the others) — fine.
- Body is a `Textarea` with `rows={10}` — at 390×844 inside the bottom-sheet, the textarea consumes a large fraction of `92svh` and Save Draft + Send Now buttons may end up clipped behind the iOS keyboard.
- **Issue: 3 footer buttons.** Cancel + Save draft + Send now. With the primitive's `flex-col-reverse gap-2 sm:flex-row`, on mobile they stack as Send / Save draft / Cancel — vertically tall (3 × button height + 2 × gap-2 ≈ 116–132px).
- No `Popover` recipient multi-select today; recipients are auto-derived server-side from the fund. So the Phase-04 audit hint about `Popover.Portal` clipping is **moot** — no popover in this dialog. The "Fund (optional)" `Select` uses Radix Select which already portals.
- Buttons `size="sm"` — tap-target issue.
- Subject input `autoFocus` opens iOS keyboard immediately on mount — fine on bottom-sheet, but the body `<Textarea>` is below the fold. Acceptable.

### `components/letters/LetterDetail.tsx`

- Mounted in Sheet on `LettersPage`. Same single-scroll-container shape as the other details.
- KPI grid `grid-cols-3` with NO `md:` — at 390px, three columns of large numbers ("Recipients / Delivered / Read") are tight but each cell is a small int + label, fine.
- Letter body is rendered as `<p class="whitespace-pre-wrap font-sans text-[14px] leading-[1.65]">{letter.body}</p>` — no `max-w-` cap. With the wrapper at full sheet width and `whitespace-pre-wrap`, long lines wrap. ✓ No horizontal scroll.
- Recipients `DataTable` has 3 columns (Recipient / Delivered / Read). Delivered/Read columns are formatted timestamps `"02 May 2026, 14:30"`. At 390px the three columns are 1 wide name col + 2 ~110px timestamp cols ≈ 350–380px. Tight but should fit. Wrap in `overflow-x-auto` defensively.
- No tabs in `LetterDetail` — the audit note about `TabsList` overflow doesn't apply here.
- Send Now action button is `size="sm"` — tap-target issue, same as siblings.

### `components/funds/FundCreateDialog.tsx`

- `DialogContent` is `sm:max-w-xl`.
- Two `grid-cols-1 md:grid-cols-2` pair rows for vintage/currency and strategy/target. ✓
- **Issue: native `<select id="fund-status">` is hand-rolled** (line 174–185) with `h-9 ... text-sm`. No `text-base md:text-sm` shim → iOS will zoom the page when the user taps it. Spec wants 16px floor on mobile.
- Buttons `size="sm"` — tap-target.
- Currency input: `value.toUpperCase()` on change is fine but uppercase IME handling on iOS can be glitchy; not flagged for this phase.

### `components/funds/FundEditDialog.tsx`

- Identical structure to `FundCreateDialog`. Same findings: native `<select>` zooms on iOS, small tap targets.

### `components/investors/InvestorCreateDialog.tsx`

- `DialogContent` is `sm:max-w-xl`. Form is short (Name / Code+Type pair / Accredited checkbox / Notes). All correct.
- Code/Type pair already `grid-cols-1 md:grid-cols-2`. ✓
- Inputs/Textarea inherit primitive 16px floor. ✓
- Buttons `size="sm"` — tap-target.

### `components/tasks/TaskCreateDialog.tsx`

- `DialogContent` is `sm:max-w-xl`. Form is title / description / fund+assignee pair / due date.
- `Select` components used for fund + assignee — Radix Select portals out of the dialog cleanly. ✓
- Already `grid-cols-1 gap-4 md:grid-cols-2` on the fund/assignee row. ✓
- Inputs and Textarea inherit 16px floor.
- Buttons `size="sm"` — tap-target.

## Cross-cutting issues to fix in subsequent tasks

1. **Tap targets on dialog primary/secondary buttons.** Every create/compose dialog uses `size="sm"` (h-8 / 32px). Add `min-h-11 md:min-h-9` to the *primary* action and make it `w-full md:w-auto`. Cancel can stay `sm` but should also get `min-h-11 md:min-h-9` for consistency since they live in the stacked-reverse footer column on mobile.
2. **Footer safe-area padding.** Bottom-sheet primitive already pads its content by `calc(env(safe-area-inset-bottom)+1.5rem)`. Adding `pb-[env(safe-area-inset-bottom)]` on the footer wrapper is redundant but harmless; spec calls for it explicitly so apply for consistency.
3. **Native `<select>` in Fund dialogs.** Either swap to the Radix `Select` component (matches every other dialog) or add `text-base md:text-sm` to the existing class string. Swapping is cleaner.
4. **Detail-component stickiness.** `CapitalCallDetail`, `DistributionDetail`, `DocumentDetail`, `LetterDetail` need: outer container is `flex h-full flex-col`, body section is `flex-1 overflow-y-auto`, header is `sticky top-0 bg-surface z-10 border-b py-3`, footer is a sticky action bar. **Caveat:** these live in a `Sheet` whose own container already does the scrolling. Refactor will move that responsibility into the detail components — verify nothing breaks visually on desktop where they have always rendered fine.
5. **Detail-component tables.** Wrap each `DataTable` in `overflow-x-auto`. For `CapitalCallDetail` and `DistributionDetail`, also offer a card-list (`md:hidden` cards / `hidden md:block` table) since the inline payment input + button row is meaningfully wider than the rest. No existing pattern to copy — introduce one.
6. **`DocumentUploadDialog` file picker visibility.** Reduce vertical padding on the form (`gap-4` → `gap-3`), and add a button-styled "Choose file" trigger on top of the bare `<input type="file">` so there's a 44pt tap target. The Phase-04 hint about hiding a dropzone on mobile is not applicable — no dropzone exists.
7. **`LetterComposeDialog` recipient picker.** No `Popover.Portal` issue today; future work item only.
