# Phase 01: Fix Dialog Readability + Mobile Bottom-Sheets

The visible bug today is that detail/review popups (Capital Calls, Distributions, Documents, Letters, Funds, Investors, Tasks) render transparent and unreadable — the shadcn primitives ship with `bg-background`/`text-foreground` tokens that EdenScale's theme (`index.css`) never defined. EdenScale uses `--color-surface`, `--color-page`, `--color-ink-*`, etc. Phase 01 fixes the root cause in the shared dialog/sheet/popover/dropdown primitives, then makes Dialog responsive: centered modal on `md+`, slide-up bottom-sheet on mobile. After this phase the popups will be solid, legible, and feel native on a phone — and every call site (CapitalCallDetail, DistributionDetail, DocumentDetail, LetterDetail, all create/edit/compose/upload dialogs) inherits the fix automatically.

## Tasks

- [x] Audit existing surface tokens and primitive call sites:
  - Read `frontend/src/index.css` and confirm the EdenScale tokens exposed via `@theme` (`--color-surface`, `--color-page`, `--color-raised`, `--color-sunken`, `--color-ink-900`, `--color-parchment-*`, `--border-hairline`, `--border-default`)
  - Grep `frontend/src/components/ui` for `bg-background`, `text-foreground`, `text-muted-foreground`, `bg-popover`, `bg-card`, `bg-accent`, `bg-secondary`, `border-input`, `ring-ring` so no stray default-shadcn tokens remain
  - Reuse-aware: do NOT introduce new color names — every replacement must use a token already present in `index.css`

- [x] Replace shadcn default tokens with EdenScale tokens across primitives that render floating surfaces:
  - `frontend/src/components/ui/dialog.tsx` — `DialogContent` background → `bg-surface`, body text → `text-ink-900`, border → `border-[color:var(--border-hairline)]`, shadow → `shadow-xl`, ensure overlay is `bg-[color:var(--bg-overlay)]`
  - `frontend/src/components/ui/alert-dialog.tsx` — same replacements as Dialog (Content/Overlay/Title/Description)
  - `frontend/src/components/ui/sheet.tsx` — sheet content `bg-surface text-ink-900` with `border-[color:var(--border-hairline)]`; overlay `bg-[color:var(--bg-overlay)]`
  - `frontend/src/components/ui/popover.tsx` — `bg-surface text-ink-900 border-[color:var(--border-hairline)] shadow-lg`
  - `frontend/src/components/ui/dropdown-menu.tsx` — content `bg-surface text-ink-900`, item hover `bg-parchment-200`, separator `bg-[color:var(--border-hairline)]`
  - `frontend/src/components/ui/command.tsx` — `bg-surface text-ink-900`, input `border-[color:var(--border-hairline)]`, item active state `bg-parchment-200`
  - `frontend/src/components/ui/tooltip.tsx` — `bg-conifer-700 text-parchment-50` (inverse) using existing tokens
  - DialogTitle keeps `font-semibold` but switch to `font-display` to match the rest of the app

- [x] Make Dialog responsive — centered on desktop, bottom-sheet on mobile:
  - Update `DialogContent` in `frontend/src/components/ui/dialog.tsx` so on `<md` it is anchored bottom (`bottom-0 left-0 right-0 top-auto translate-x-0 translate-y-0`), full width, `max-h-[92svh] overflow-y-auto`, with a 16px top radius (`rounded-t-lg rounded-b-none`); on `md+` keep the existing centered modal (translate-50 / translate-50, `sm:max-w-lg`, `rounded-lg`)
  - Use `data-[state=open]:animate-in data-[state=closed]:animate-out` plus `slide-in-from-bottom`/`slide-out-to-bottom` on mobile, `zoom-in-95`/`zoom-out-95` on `md+` (Tailwind `tw-animate-css` is already wired up)
  - Add a small visible drag-handle bar at the top of the bottom-sheet variant (`mx-auto h-1.5 w-10 rounded-full bg-ink-300`) shown only on `<md` via `md:hidden`
  - Move the close `X` button so it stays accessible on mobile (`top-3 right-3`) and ensure 44×44px hit target with `p-2`

- [x] Make AlertDialog and Sheet feel right on mobile:
  - `alert-dialog.tsx` — same responsive treatment as Dialog (bottom-sheet on `<md`)
  - `sheet.tsx` — when `side="right"` or `side="left"` on `<md`, expand to `w-full` (instead of partial width) and add safe-area padding (`pb-[env(safe-area-inset-bottom)]`)
  - Ensure Sheet's overlay/content uses the same EdenScale tokens

- [x] Verify the fix end-to-end with the dev server (use webapp-testing skill if available):
  - Run `make start-frontend` and `make start-backend` in the background
  - Open `/funds`, `/investors`, `/capital-calls`, `/distributions`, `/documents`, `/letters`, `/tasks` — trigger each detail/create dialog
  - Confirm dialogs are opaque, readable, with EdenScale typography (Inter Tight body, Cormorant for titles)
  - Resize browser to ~390px width or DevTools "iPhone 14" preset and confirm dialogs slide in from the bottom, fill the width, and have a visible drag-handle
  - Capture before/after notes inline (no separate doc) — if any dialog still looks broken, fix the offending primitive call site directly

- [x] Run quality gates and capture a screenshot of the polished bottom-sheet:
  - `cd frontend && pnpm run lint` (tsc only, no eslint configured)
  - `make lint` (backend lint must still pass — should be untouched)
  - Save one mobile screenshot of an open detail dialog to `Auto Run Docs/2026-04-30-Edenscale/Working/phase-01-mobile-dialog.png` for the user to review

## Notes (Phase 01 completion — 2026-04-30)

**Implementation summary**
- Replaced default shadcn tokens (`bg-background`, `text-foreground`, `text-muted-foreground`, `bg-popover`, `bg-accent`, `bg-secondary`, `bg-border`, `bg-foreground`) with EdenScale tokens (`bg-surface`, `text-ink-900`, `text-ink-500`, `bg-parchment-200`, `bg-conifer-700`, `text-parchment-50`, `border-[color:var(--border-hairline)]`, `bg-[color:var(--border-hairline)]`) across `dialog.tsx`, `alert-dialog.tsx`, `sheet.tsx`, `popover.tsx`, `dropdown-menu.tsx`, `command.tsx`, `tooltip.tsx`. No new color names introduced — all replacements reuse tokens already declared in `frontend/src/index.css`.
- Overlays now use `bg-[color:var(--bg-overlay)]` (a tinted Conifer black at 0.55 alpha) instead of plain `bg-black/50`, giving the modal scrim the warm-cool wash of the EdenScale palette.
- Tooltip inverted to `bg-conifer-700 text-parchment-50` (arrow follows) per spec.
- DialogTitle / AlertDialogTitle / SheetTitle picked up `font-display` so popup headlines render in Cormorant Garamond and match page heroes.

**Responsive Dialog / AlertDialog**
- Default classes describe the desktop centered modal (`top-50% left-50% -translate-x-1/2 -translate-y-1/2 sm:max-w-lg rounded-lg zoom-in-95`).
- `max-md:` overrides flip the dialog into a full-width bottom-sheet (`max-md:inset-x-0 max-md:bottom-0 max-md:top-auto max-md:max-w-none max-md:rounded-t-lg max-md:rounded-b-none max-md:max-h-[92svh] max-md:overflow-y-auto max-md:slide-in-from-bottom`), neutralising the desktop zoom with `max-md:zoom-in-100`.
- Initial attempt used mobile-first defaults plus `md:` overrides — that didn't work because `md:max-w-[calc(100%-2rem)]` outranked `sm:max-w-lg` and the dialog stretched edge-to-edge on desktop. Inverting to desktop-first + `max-md:` cleared this up (verified visually below).
- Mobile drag-handle (`mx-auto h-1.5 w-10 rounded-full bg-ink-300 md:hidden`) sits above the title; close `X` is `top-3 right-3` with a 44×44 hit target.

**Sheet**
- On `<md`, side="right" / side="left" sheets expand to `w-full` and pick up `md:w-3/4 sm:max-w-sm` only at md+. `pb-[env(safe-area-inset-bottom)]` is applied to the content for iOS gesture-bar safety.

**Verification**
- Type check (`pnpm run lint` → `tsc --noEmit`) passes.
- Backend `make lint` still green (untouched).
- Captured at iPhone 14 width (390×844) and 1280×800 desktop. Both opaque, legible, EdenScale typography. Mobile screenshot saved to `Working/phase-01-mobile-dialog.png`; desktop comparison at `Working/phase-01-desktop-dialog.png`. Playwright capture script kept at `Working/dialog_screenshot.py` for re-runs.
- The "Connection failed" toast in screenshots is just the toast notification produced by the unauthenticated openapi-fetch middleware in our smoke setup — it does not affect dialog rendering.
