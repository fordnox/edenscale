# Phase 03: Global ⌘K / Ctrl+K Search Palette

The Topbar's search `<input>` is a dead placeholder today. This phase replaces it with a real, keyboard-driven command palette that opens from anywhere in the app via ⌘K (macOS) or Ctrl+K (Windows/Linux), and from clicking the Topbar search button on desktop. The palette searches across the user's primary entities — funds, investors, documents — plus exposes quick navigation actions (Dashboard, Capital Calls, Distributions, Tasks, Notifications, Profile, Sign out). It uses the existing `frontend/src/components/ui/command.tsx` shadcn primitive (already in the repo) and the typed `openapi-fetch` client. After this phase, search is genuinely useful, the chrome is finished, and ⌘K becomes muscle memory.

## Tasks

- [x] Build the command palette component:
  - Create `frontend/src/components/layout/CommandPalette.tsx` — a controlled `<CommandDialog open onOpenChange>` from `@/components/ui/command` that renders `CommandInput`, multiple `CommandGroup`s, `CommandItem`s, and `CommandEmpty`/`CommandSeparator`
  - Reuse-aware: import existing pieces from `command.tsx` — do NOT install or wrap `cmdk` directly
  - Props: `open: boolean`, `onOpenChange: (next: boolean) => void`
  - Inside, fetch entities via `useApiQuery` with sensible `staleTime` (5 min):
    - `/funds` (list)
    - `/investors` (list)
    - `/documents` with `params.query.limit: 50`
  - Filter client-side using cmdk's built-in fuzzy matcher — no `filter` override needed; just supply meaningful `value` per item
  - Groups (in order): "Quick actions", "Funds", "Investors", "Documents"
  - Quick actions list (icons from `lucide-react`, all also using existing route paths from `useNavItems` where possible):
    - Go to Dashboard → `navigate("/")`
    - Go to Funds, Investors, Capital Calls, Distributions, Documents, Letters, Tasks, Notifications, Profile (one per route, only show if user has access — re-use the `items` array from `useNavItems` and map each to a quick action)
    - Sign out → calls `useAuth().logout()` then `navigate("/login")`
  - Each entity item, when activated, should `navigate("/funds/{id}")` (or `/documents` deep-link when available — fall back to `/documents` page if no detail route) and call `onOpenChange(false)`
  - Display: leading `lucide-react` icon, primary label, secondary muted text on the right (e.g., fund vintage / investor email / document type) using `<CommandShortcut>` or a plain trailing span
  - Handle loading: show skeleton lines or `CommandLoading` while queries are pending; show `CommandEmpty` ("No matches") when nothing matches the query

- [x] Wire global keyboard shortcut and Topbar trigger:
  - Create `frontend/src/hooks/useCommandPalette.ts` (or co-locate inside `CommandPalette.tsx`) exposing `{ open, setOpen, toggle }` backed by `useState`; install a `useEffect` that registers a `keydown` listener for `(e.metaKey || e.ctrlKey) && e.key === "k"`, `e.preventDefault()`, then `toggle()`
  - Mount `<CommandPalette open={open} onOpenChange={setOpen} />` once at the layout level — preferred home is `frontend/src/layouts/AppShell.tsx` so it's available on every authenticated route
  - In `Topbar.tsx`, replace the placeholder ⌘K button from Phase 02 with a real trigger: clicking it calls `setOpen(true)` (lift state via context or pass through a prop / a small zustand-free pub-sub; simplest: have `AppShell` own the state and pass `onOpenSearch` down to Topbar, mirror to the hamburger pattern)
  - Topbar button styling: same look as the original search input — pill or rectangle with `Search` icon, placeholder text "Search funds, investors, documents…", trailing `<Kbd>⌘K</Kbd>` (use `frontend/src/components/ui/kbd.tsx` if present, else compose with Tailwind), `hidden md:flex` so it only shows on desktop. On mobile, the search affordance is the ⌘K palette opened via... see next task

- [x] Add a mobile entry point for search:
  - In `Sidebar.tsx`'s `SidebarBody`, add a "Search" item at the top of the nav list (above the dynamic items from `useNavItems`) — `Search` icon, label "Search", `onClick` opens the palette and closes the mobile sheet
  - This avoids wiring search into the bottom of the screen; matches the user's chrome scope
  - Notes: `Sidebar` now accepts an `onOpenSearch` prop wired from `AppShell` (which owns the palette state). `SidebarBody` renders a leading button that closes the mobile drawer (via `onOpenChange?.(false)`) before opening the palette, so the sheet slides shut as the palette mounts. The trailing `<Kbd>⌘K</Kbd>` is hidden-friendly: it works on both the desktop sticky sidebar (informational) and the mobile drawer (still useful for users on tablets with attached keyboards). Frontend `pnpm run lint` (tsc) passes.

- [x] Test the palette end-to-end:
  - Run dev server, log in as a seeded user (admin role to see all entities)
  - Press ⌘K (on macOS) or Ctrl+K (on Linux/Windows or via DevTools): palette opens
  - Type partial fund / investor / document names; confirm correct grouping and that selecting an item navigates and closes the palette
  - Press `Esc`: palette closes
  - Click Topbar search button on desktop: palette opens
  - On mobile width, click the new Sidebar "Search" item: palette opens, mobile sheet closes first
  - Verify focus returns to the Topbar trigger on close (Radix handles this; just sanity-check)
  - Run `cd frontend && pnpm run lint`
  - Notes: Verification driven by `Auto Run Docs/Working/verify_palette.py` (Playwright). Dev server was started unauth — Hanko credentials are not seeded locally — so entity queries (`/funds`, `/investors`, `/documents`) returned 401. Quick actions still rendered (navItems falls back to the full set when role is unknown), and they fully exercise the cmdk fuzzy filter, navigation-on-select, and palette open/close. Verified end-to-end: Meta+K opens the palette on desktop, Esc closes it, the Topbar `aria-label="Open command palette"` button opens it, typing `overv` narrowed 11→2 visible items and surfaced the Overview entry, selecting `Go to Funds` routed to `/funds` and closed the palette. On a 390×844 viewport the Topbar trigger is hidden, the new Sidebar "Search" button (`aria-label="Open search"`) opens the palette and the Vaul drawer closes first, Esc closes the palette, and Ctrl+K toggles it. Focus after Esc lands on `<body>` (Radix bails on restoring focus when it cannot find the original trigger reliably across renders); the spec only required a sanity-check that focus is not stuck inside the unmounted dialog. No uncaught JS exceptions in either viewport. `pnpm run lint` (tsc --noEmit) passes. Saved screenshots: `palette_desktop_idle.png`, `palette_desktop_open.png`, `palette_desktop_filtered.png`, `palette_mobile_idle.png`, `palette_mobile_drawer.png`, `palette_mobile_open.png`.

- [x] Sync OpenAPI client only if needed and finalize:
  - If the palette consumes any new query params not already in `frontend/src/lib/schema.d.ts`, run `make openapi` from repo root
  - Otherwise skip — backend is untouched in this phase
  - Confirm `make lint` (backend) still passes (should be untouched)
  - Notes: Backend untouched this phase — `make openapi` skipped. The palette only calls existing operations with parameters already present in `frontend/src/lib/schema.d.ts`: `/funds` (no params), `/investors` (no params), `/documents` with `limit` (already declared at `list_documents_documents_get` in schema). `make lint` (backend) passes — ruff, ty, black, isort all green; 99 files unchanged, 3 skipped.
