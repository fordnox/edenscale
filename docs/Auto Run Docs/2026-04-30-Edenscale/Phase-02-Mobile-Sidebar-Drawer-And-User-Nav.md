# Phase 02: Mobile Sidebar Drawer + User Nav at Bottom-Left

The sidebar (`frontend/src/components/layout/Sidebar.tsx`) is currently `hidden md:flex` — on mobile there is no navigation at all. The user-menu/profile lives in the top-right of the Topbar, but the user wants it permanently anchored to the **bottom-left of the sidebar** (both desktop and mobile). The Topbar currently shows a notifications bell that should be removed (notifications already live as a sidebar item via `useNavItems`). This phase introduces a swipe-to-close mobile drawer for the sidebar, makes the existing static profile card at the bottom of the sidebar interactive (dropdown with Profile / Sign out), and slims the Topbar down to just the search affordance. After this phase the chrome is mobile-first while looking identical on desktop.

## Tasks

- [x] Refactor `Sidebar.tsx` to be controllable and reusable across desktop and mobile:
  - Extract the inner contents (logo header, nav list, footer profile) into a `SidebarBody` sub-component inside `frontend/src/components/layout/Sidebar.tsx` so it can be rendered both inline (desktop) and inside a `Sheet` (mobile)
  - Desktop wrapper stays `aside ... sticky top-0 hidden h-svh w-[260px] ... md:flex`
  - Mobile wrapper uses `Sheet` from `@/components/ui/sheet` with `side="left"`, controlled `open`/`onOpenChange` via a new prop, `w-[280px] sm:w-[320px]` content, no padding overrides — relies on Phase 01 token fixes
  - Auto-close the mobile sheet on route change (use `useLocation` from `react-router-dom`; close in a `useEffect` watching `pathname`)
  - Reuse-aware: `Sheet` already exists at `frontend/src/components/ui/sheet.tsx` — do NOT add a new drawer library

- [x] Convert the bottom profile block into an interactive user-menu (replacing the static initials card):
  - At the bottom of `SidebarBody`, replace the read-only `div` with a `DropdownMenu` whose trigger is the same initials + name + tagline visual (full-width button, `hover:bg-parchment-100`, focus ring using `--conifer-600`)
  - Reuse the existing user-menu logic from `frontend/src/components/user-menu.tsx` and/or the topbar dropdown — pull the same `useApiQuery("/users/me")`, `useAuth().logout`, `deriveInitials` pattern; if `user-menu.tsx` already encapsulates this, prefer importing it
  - Menu items: Profile (→ `/profile`), Organization settings (→ `/organization-settings`, only if role === "admin"), Sign out (calls `logout()` then `navigate("/login")`)
  - DropdownMenu `side="top" align="start"` so it opens upward and aligns with the bottom-left anchor
  - Ensure 44px minimum hit target on mobile

- [x] Add a hamburger trigger and rebuild `Topbar.tsx`:
  - Add a state in `frontend/src/layouts/AppShell.tsx` (or hoist to the Topbar+Sidebar layer) controlling the mobile sidebar `open` prop — pass it down to both `Topbar` (which renders the trigger) and `Sidebar` (which renders the sheet)
  - In `frontend/src/components/layout/Topbar.tsx`:
    - Remove the entire `Bell`/notifications `Link` block — notifications are reached via the sidebar's existing nav item
    - Remove the user-menu `DropdownMenu` block from the Topbar (now lives only in the sidebar)
    - Add a `Menu` icon button (from `lucide-react`) on the left, visible only on `<md` (`md:hidden`), with `aria-label="Open navigation"`, that calls `onOpenSidebar()`
    - Replace the desktop search `<input>` with a button that triggers the ⌘K palette (Phase 03 wires the palette itself; for now the button just shows the styled placeholder + a `<Kbd>⌘K</Kbd>` hint and is disabled or `onClick` opens a placeholder `console.log("cmdk")`); button is `hidden md:flex`
    - Compact mobile layout: `px-4 py-3` instead of `px-8 py-4`
  - Drop now-unused imports (`Bell`, `LogOut`, `UserIcon`, `DropdownMenu*`, `useApiQuery` for notifications)

- [x] Polish mobile interactions on the sidebar drawer:
  - Add swipe-to-close: Radix's Sheet primitive (Vaul-style) supports drag to dismiss when used as a Drawer; if `Sheet` lacks gesture support, wrap the mobile variant in the existing `drawer.tsx` (Vaul) component and only swap-in for `<md`. Reuse-aware: check `frontend/src/components/ui/drawer.tsx` first to see if Vaul is already installed before adding it
  - Ensure all nav items have `min-h-11` (44px) padding on mobile via `py-3 md:py-2.5`
  - Confirm `useNavItems` already gates Notifications/Audit-log/Org-settings by role — no changes there

  Notes (2026-04-30):
  - Swapped the mobile `Sheet` in `Sidebar.tsx` for the existing Vaul-based `Drawer` (`@/components/ui/drawer`) with `direction="left"` — Vaul supplies native drag-to-dismiss. Desktop `<aside>` is unchanged. Vaul was already installed (no new dep).
  - NavLink className now: `min-h-11 md:min-h-0 ... px-3 py-3 md:py-2.5` — 44px tap target on mobile, original spacing on desktop.
  - Confirmed gating: `useNavItems` returns admin-only Audit Log; Notifications shows for all roles by design (FULL_ITEMS + LP_ITEMS); Organization settings is gated `role === "admin"` in the sidebar dropdown.
  - Updated `drawer.tsx` overlay to `bg-[color:var(--bg-overlay)]` to match the Sheet overlay token (drawer.tsx is only consumed by Sidebar today).
  - `pnpm run lint` (tsc --noEmit) passes.

- [x] Verify mobile + desktop chrome end-to-end:
  - With dev server running, on desktop confirm: sidebar visually identical, bottom-left profile is now a dropdown that opens upward with Profile / Sign out, Topbar has no bell and no profile dropdown
  - At ~390px width confirm: hamburger appears top-left of Topbar, taps open the sidebar as a sheet, taps a nav item navigates and auto-closes the sheet, drag/swipe-left dismisses the sheet, profile dropdown opens upward and is reachable from the bottom of the sheet
  - Run `cd frontend && pnpm run lint` and fix any unused-import / type errors introduced by the Topbar refactor
  - If the topbar becomes empty on desktop except for the ⌘K button, that's expected — Phase 03 fills it

  Verification (2026-04-30):
  - `pnpm run lint` (tsc --noEmit) passes with zero errors — no unused-import / type fallout from the Topbar refactor.
  - Drove the live Vite dev server with Playwright at 1280×800 and 390×844 viewports (`Auto Run Docs/Working/verify_chrome.py`, `verify_mobile_usermenu.py`).
  - Desktop confirmed: `aside` sidebar visible, hamburger hidden, ⌘K button visible, **0** bell links and **0** dropdown triggers in `<header>`, sidebar bottom user-menu trigger visible, dropdown opens upward (content top above trigger top) with `Profile` / `Sign out` items (no `Organization settings` because the unauthenticated dev fallback role isn't admin — gating works as designed).
  - Mobile confirmed: desktop `<aside>` hidden, hamburger visible, ⌘K hidden, hamburger tap opens Vaul drawer with 9 nav items, tapping a nav link navigates (e.g. `/funds`) and auto-closes the drawer (route-change `useEffect`), bottom user-menu trigger inside the drawer opens upward with `Profile` / `Sign out`, swipe-left from the right edge of the drawer to off-screen dismisses it (Vaul gesture).
  - 404 console errors observed during the run are from unauthenticated `/users/me` and `/dashboard/overview` calls (no Hanko session in headless context) — unrelated to chrome and matched by an existing toast.
  - Screenshots captured under `Auto Run Docs/Working/`: `desktop_default.png`, `desktop_usermenu.png`, `mobile_default.png`, `mobile_drawer_open.png`, `mobile_drawer_usermenu.png`, `mobile_after_swipe.png`.
