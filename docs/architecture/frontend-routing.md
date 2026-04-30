---
type: reference
title: Frontend Routing
created: 2026-04-29
tags:
  - architecture
  - frontend
  - react
related:
  - '[[System-Overview]]'
  - '[[RBAC-Model]]'
---

# Frontend Routing

The SPA is a single React Router v6 tree declared in [`frontend/src/App.tsx`](../../frontend/src/App.tsx). Two layouts exist: `AppShell` for the authenticated dashboard, and a bare layout for `/login`. Page-level role gating is applied with `<RequireRole>` (see [[RBAC-Model]]); sidebar-level filtering is applied with `useNavItems()`.

## Route table

| Path                      | Component                       | Layout       | Sidebar visibility (per role)                | Page-level role gate            |
| ------------------------- | ------------------------------- | ------------ | -------------------------------------------- | ------------------------------- |
| `/`                       | `DashboardPage`                 | `AppShell`   | admin · fund_manager · lp                    | none (data is role-scoped)      |
| `/funds`                  | `FundsPage`                     | `AppShell`   | admin · fund_manager · lp                    | none (data is role-scoped)      |
| `/funds/:fundId`          | `FundDetailPage`                | `AppShell`   | (deep-link only)                             | none (404 if not visible)       |
| `/investors`              | `InvestorsPage`                 | `AppShell`   | admin · fund_manager · lp                    | none (data is role-scoped)      |
| `/calls`                  | `CapitalCallsPage`              | `AppShell`   | admin · fund_manager (lp: hidden in sidebar) | none (data is role-scoped)      |
| `/distributions`          | `DistributionsPage`             | `AppShell`   | admin · fund_manager (lp: hidden in sidebar) | none (data is role-scoped)      |
| `/documents`              | `DocumentsPage`                 | `AppShell`   | admin · fund_manager · lp                    | none (data is role-scoped)      |
| `/letters`                | `LettersPage`                   | `AppShell`   | admin · fund_manager · lp                    | none (data is role-scoped)      |
| `/tasks`                  | `TasksPage`                     | `AppShell`   | admin · fund_manager (lp: hidden in sidebar) | none (data is role-scoped)      |
| `/notifications`          | `NotificationsPage`             | `AppShell`   | admin · fund_manager · lp                    | none (per-user)                 |
| `/profile`                | `ProfilePage`                   | `AppShell`   | (Topbar user menu only, not sidebar)         | none (per-user)                 |
| `/settings/organization`  | `OrganizationSettingsPage`      | `AppShell`   | (Profile page link only)                     | `RequireRole: admin, fund_manager` |
| `/audit-log`              | `AuditLogPage`                  | `AppShell`   | admin only                                   | `RequireRole: admin`            |
| `/login`                  | `LoginPage`                     | (bare)       | n/a                                          | n/a                             |

"Sidebar visibility" controls what `useNavItems()` returns — a fund_manager has Capital Calls in the sidebar, an LP does not. The API still re-checks on the backend; hiding nav is a UX nicety, not a security boundary.

## Layouts

### `AppShell` (`frontend/src/layouts/AppShell.tsx`)

Standard authenticated chrome:

- **Sidebar** (`components/layout/Sidebar.tsx`) — consumes `useNavItems()`, role-aware. Header sub-label and footer text are role-driven (`Administrator view` / `Manager view` / `Limited partner view`).
- **Topbar** — global search, notifications bell with unread count, and user-menu (Profile / Sign out).
- **`<Outlet />`** — the page renders here.

`AppShell` itself does not check auth; it relies on the API client redirecting to `/login` on 401 (see `frontend/src/lib/api.ts`).

### `LoginPage`

Standalone — no shell. Hosts the Hanko `<hanko-auth>` web component.

### Legacy `MainLayout`

`frontend/src/layouts/MainLayout.tsx` (with `Header.tsx` + `Footer.tsx`) is retained as scaffolding for any future marketing route, but **no route currently uses it**. The previous `/profile` was migrated to `AppShell` in Phase 09.

## Sidebar role mapping

From `frontend/src/hooks/useNavItems.ts`:

```
fund_manager → [Overview, Funds, Investors, Capital Calls, Distributions,
                Documents, Letters, Tasks, Notifications]
admin        → fund_manager set + [Audit Log]
lp           → [Overview, Funds, Investors, Documents, Letters, Notifications]
unknown      → fund_manager set (default during loading; the actual route is
                still gated by RequireRole / API checks, so this is safe)
```

`Profile` and `Organization Settings` are reachable from the Topbar user menu and the Profile page; they are **not** in the sidebar.

## Conventions

- **Route declaration** — every route is declared in `App.tsx`. Do not introduce nested route trees in pages; if a page needs subroutes, lift them to `App.tsx` and use `<Outlet />`.
- **Path alias** — `@/*` resolves to `frontend/src/*`. Configured in both `vite.config.ts` and `tsconfig.json`.
- **API client** — `frontend/src/lib/api.ts` exports a typed `openapi-fetch` client built from `frontend/src/lib/schema.d.ts` (regenerated via `make openapi`). Auto-attaches the Hanko session token via `getSessionToken()` and surfaces non-401 errors through `sonner` toasts.
- **Data hooks** — `useApiQuery` and `useApiMutation` (`frontend/src/hooks/`) wrap TanStack Query against the typed client. The standard mutation pattern is `useApiMutation` + `queryClient.invalidateQueries({ queryKey: [path] })` + sonner toast — see `InvestorDetailPanel`'s `invalidateInvestorScopes` helper as the canonical example.
- **Role gating** — wrap a whole page with `<RequireRole allowed={[...]}>` in the page module itself, not in `App.tsx`, so the gating travels with the page and the route declaration stays uniform.

## Adding a new page

1. Create `frontend/src/pages/MyPage.tsx`. Follow the established `PageHero` + stacked `Card` layout used by `NotificationsPage` / `TasksPage` / `ProfilePage`.
2. If role-restricted, wrap the page contents in `<RequireRole allowed={[...]}>`.
3. Add the `<Route>` to `App.tsx`, inside the `AppShell` block.
4. If the page should appear in the sidebar, add a `NavItem` constant in `useNavItems.ts` and slot it into the appropriate role's array.
5. Update this doc's route table.
