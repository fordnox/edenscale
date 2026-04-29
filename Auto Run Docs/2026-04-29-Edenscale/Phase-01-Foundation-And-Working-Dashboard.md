# Phase 01: Foundation And Working Dashboard

This phase establishes the project foundation by porting EdenScale design tokens (colors, typography, fonts) into the production `frontend/`, generating the full SQLAlchemy schema and Alembic migration that mirrors `db.dbml`, and wiring a real end-to-end Dashboard page that calls a new `/dashboard/overview` endpoint. By the end of this phase, the backend boots with the complete schema migrated, the frontend renders the EdenScale-branded Dashboard with live data from the API, and the `make lint` / `make test` / `make openapi` commands all pass green.

## Tasks

- [x] Read existing project context to ground the rest of the work:
  - Read `CLAUDE.md`, `README.md`, `Makefile`, `db.dbml`
  - Read `design/colors_and_type.css`, `design/SKILL.md`, `design/README.md`
  - Read `edenscale/src/App.tsx`, `edenscale/src/index.css`, `edenscale/src/components/layout/Sidebar.tsx`, `edenscale/src/components/layout/Topbar.tsx`, `edenscale/src/pages/DashboardPage.tsx`, `edenscale/src/data/mock.ts`, `edenscale/src/lib/format.ts`, `edenscale/src/lib/utils.ts`
  - Read `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/main.tsx`, `frontend/src/lib/api.ts`, `frontend/src/layouts/MainLayout.tsx`, `frontend/package.json`, `frontend/vite.config.ts`
  - Read `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/core/auth.py`, `backend/app/models/user.py`, `backend/app/schemas/user.py`, `backend/app/routers/dashboard.py`, `backend/app/routers/users.py`, `backend/app/repositories/user_repository.py`, `backend/alembic.ini`, and list the contents of `backend/app/alembic/versions/`
  - Note any existing patterns to reuse (router → repository → model layering, `Depends(get_db)`, Pydantic BaseModel style) so later tasks do not re-invent them

  **Notes from orientation pass (Iteration 00001):**
  - **Stack:** FastAPI + SQLAlchemy + Alembic backend (currently a single `users` table with Hanko-style String(36) IDs); React 19 + Vite 8 + Tailwind v4 + React Router v7 frontend with Hanko auth and an `openapi-fetch` typed client at `@/lib/api`.
  - **Backend layering:** routers (`backend/app/routers/`) → repositories (`backend/app/repositories/`) → models (`backend/app/models/`); Pydantic schemas in `backend/app/schemas/` use `model_config = {"from_attributes": True}`. `get_current_user` is wired at the `include_router` level in `app/main.py`, never per-route. `Base` is exported from `app/core/database.py`.
  - **Existing User model is Hanko-shaped** (`id` = String(36), `email`, `name`, `picture`) — Phase 1 will replace it with the dbml-shaped User and keep `hanko_subject_id` indexed alongside. There is one existing migration `3c9336ee4c60` that creates the old `users` table — it will need to be replaced/superseded by the new initial schema migration.
  - **Frontend index.css is currently shadcn defaults** (oklch black/white, `tw-animate-css`) — Task 2 will replace it wholesale with the EdenScale token block from `edenscale/src/index.css`.
  - **MainLayout** wraps public/protected pages with header+footer; `/login` is standalone. Phase 1 will introduce a parallel `AppShell` for the dashboard area without disturbing `MainLayout`.
  - **Prototype `App.tsx`** drives navigation through a `Route` enum + `useState`; the production port must use `react-router-dom` `<NavLink>` instead.
  - **Mock data shape** in `edenscale/src/data/mock.ts` is a useful map of which fields the Dashboard cards consume (committed/called/distributed/nav per fund, capital-call status filter for "scheduled/sent/overdue", task `status !== "done"`, etc.) — these will inform the Pydantic response schema.
  - **dbml schema:** 18 tables + 10 enums; PK is `int` autoincrement everywhere; money is `decimal(18,2)`; composite uniques on `(fund_id, user_id)`, `(fund_id, investor_id)`, `(capital_call_id, commitment_id)`, `(distribution_id, commitment_id)`, `(communication_id, user_id)`.
  - **Lint/test pre-commit gates:** `make test` (pytest), `make lint` (ruff/ty/black/isort, excludes `tests`/`.venv`/`app/alembic`), `make openapi` must run after any backend route/schema change.

- [x] Install design assets into the frontend:
  - Copy all eight `.woff2` files from `design/fonts/` to `frontend/public/fonts/` (create the directory if missing)
  - Replace `frontend/src/index.css` with the EdenScale token-based CSS, modeled exactly on `edenscale/src/index.css` (same `@font-face` rules pointing to `/fonts/*`, same `:root` token block, same `@theme` block with `--color-conifer-*`, `--color-brass-*`, `--color-parchment-*`, `--color-ink-*`, `--color-status-*`, `--color-page`, `--color-surface`, `--color-raised`, `--color-sunken`, fonts, radii, motion, plus the `@layer base` body defaults and `@layer components` `.es-display`, `.es-eyebrow`, `.es-quote`, `.es-numeric`, `.es-numeric-display`, `.es-rule`, `.es-rule-strong` classes)
  - Verify Tailwind v4 is already on (it is — see `frontend/vite.config.ts` and `package.json`); no extra config files are needed

  **Notes (Iteration 00001):**
  - Created `frontend/public/fonts/` and copied all 8 `.woff2` files (Cormorant Garamond 400/400i/500/600 + Inter Tight 400/500/600/700) from `design/fonts/`.
  - Replaced `frontend/src/index.css` with the EdenScale token block from the prototype verbatim — `@font-face` rules, `:root` brand/surface/foreground/border vars, `@theme` block (full conifer/brass/parchment/ink/status palettes, page/surface/raised/sunken aliases, font families, `--radius-xs|sm|pill`, `--ease-standard`), `@layer base` (html/body, ::selection, :focus-visible, table tabular-nums), and `@layer components` (`.es-display`, `.es-eyebrow`, `.es-eyebrow-inverse`, `.es-quote`, `.es-numeric`, `.es-numeric-display`, `.es-rule`, `.es-rule-strong`).
  - Kept `@import "tw-animate-css";` because 13 existing shadcn UI components (`dialog`, `dropdown-menu`, `popover`, `select`, `sheet`, `toast`, `tooltip`, etc.) reference its `animate-in` / `fade-*` / `slide-*` / `zoom-*` utilities; dropping it would silently break those components without solving anything for this task. The package is already in `devDependencies`.
  - Removed the legacy shadcn `:root` / `.dark` oklch token block and the `hanko-auth` / `hanko-profile` Hanko theming block. The Hanko block referenced shadcn vars (`--foreground`, `--primary`, …) that no longer exist; without it the Hanko web component falls back to its built-in defaults — acceptable for now since Login styling is not in scope this phase. `LoginPage.tsx` still uses shadcn `bg-primary` / `text-muted-foreground` classes that no longer resolve to anything; visual regressions there are expected and will be addressed when the login page is reskinned (out of scope for Phase 1, which targets the Dashboard).
  - Verified `pnpm run build` succeeds (`vite build` 259ms, 1877 modules transformed, no errors). Pre-existing `tsconfig.json` `baseUrl` deprecation warning under TS 7-preview is unrelated to this change.

- [ ] Port shared UI primitives from the prototype into `frontend/src/components/ui/`:
  - Copy `edenscale/src/components/ui/badge.tsx`, `button.tsx`, `card.tsx`, `eyebrow.tsx`, `progress.tsx`, `stat.tsx`, `table.tsx` verbatim into `frontend/src/components/ui/` (overwrite any same-named files; preserve any existing shadcn `frontend/src/components/ui/*` files unrelated to these names)
  - Copy `edenscale/src/lib/format.ts` to `frontend/src/lib/format.ts`
  - Ensure all imports in copied files use the `@/` alias (already configured in `frontend/tsconfig.json` and `vite.config.ts`)

- [ ] Define SQLAlchemy enums and models matching every table in `db.dbml`:
  - Create `backend/app/models/enums.py` exporting Python `enum.Enum` subclasses for `UserRole`, `OrganizationType`, `FundStatus`, `CommitmentStatus`, `CapitalCallStatus`, `DistributionStatus`, `DocumentType`, `CommunicationType`, `NotificationStatus`, `TaskStatus` with values matching the dbml literals exactly
  - Replace `backend/app/models/user.py` and add new model files in `backend/app/models/` so each `Table` in `db.dbml` has a corresponding SQLAlchemy declarative model — `organization.py`, `user.py`, `fund_group.py`, `fund.py`, `fund_team_member.py`, `investor.py`, `investor_contact.py`, `commitment.py`, `capital_call.py`, `capital_call_item.py`, `distribution.py`, `distribution_item.py`, `document.py`, `communication.py`, `communication_recipient.py`, `notification.py`, `task.py`, `audit_log.py`
  - Each model: subclass the existing `Base` from `app.core.database`, declare the `__tablename__`, every column with the dbml type/nullability/default, all foreign keys via `ForeignKey("table.id")`, every unique composite index via `UniqueConstraint`, and bidirectional `relationship(...)` between parents and children where dbml has a `ref:` line
  - The `User` model retains Hanko compatibility: keep an indexed `hanko_subject_id` (varchar, nullable for now to avoid breaking existing usage) alongside the dbml columns. Keep `password_hash` nullable in practice so Hanko-only users do not require it (define it as `nullable=False, default=""` to satisfy the dbml `not null` while not requiring a real password)
  - Update `backend/app/models/__init__.py` to import every model so `Base.metadata` sees them
  - Update `backend/app/repositories/user_repository.py` only as far as needed to compile against the new `User` columns; do not add new methods yet

- [ ] Create the initial Alembic migration that builds the full schema:
  - Inspect `backend/app/alembic/env.py` and `backend/app/alembic/versions/` to confirm metadata is wired correctly; if `target_metadata` is not pointing at `app.models.Base.metadata`, fix it
  - From `backend/`, run `uv run alembic revision --autogenerate -m "initial schema from dbml"` to generate one migration; review the generated file, ensure it creates every table, enum (use `sa.Enum(... name="user_role")` etc.), foreign key, and unique constraint, and edit by hand only if autogenerate misses something
  - Run `uv run alembic upgrade head` against the local SQLite DB to confirm the migration applies cleanly; if a previous migration exists for the original `users` table, leave older migrations in place — the new migration should be additive/replacing as needed

- [ ] Add a typed Pydantic schema layer for the dashboard overview:
  - Create `backend/app/schemas/dashboard.py` with `DashboardOverviewResponse` (counts of `funds_active`, `investors_total`, `commitments_total_amount`, `capital_calls_outstanding`, `distributions_ytd_amount`, plus `recent_funds: list[FundSummary]` and `upcoming_capital_calls: list[CapitalCallSummary]` where each summary holds the minimum fields needed by the prototype Dashboard cards)
  - Mark all monetary values as `Decimal` and serialize with `model_config = ConfigDict(from_attributes=True)`

- [ ] Replace the placeholder dashboard router with a real overview endpoint:
  - Update `backend/app/routers/dashboard.py` so `GET /dashboard/overview` returns a `DashboardOverviewResponse` populated by SQL aggregates (`func.count`, `func.sum`, `func.coalesce`) over the new tables, filtered to the caller's organization when the JWT carries one (read `current_user` from `Depends(get_current_user)` and look up the matching `User` row by `hanko_subject_id`; if no row exists, fall back to returning zeros and empty arrays so the endpoint never 500s on a fresh DB)
  - Keep the existing `Depends(get_current_user)` wiring at the `include_router` level — do not duplicate it on the route

- [ ] Regenerate the OpenAPI client and confirm types are in sync:
  - From the repo root, run `make openapi`
  - Confirm `backend/openapi.json` contains the new `/dashboard/overview` schema
  - Confirm `frontend/src/lib/schema.d.ts` now exposes `paths["/dashboard/overview"]` and the new response types

- [ ] Port the Dashboard layout and page into the production frontend:
  - Create `frontend/src/components/layout/Sidebar.tsx` and `frontend/src/components/layout/Topbar.tsx` based on the prototype copies, but adapt the navigation to use `react-router-dom`'s `<NavLink>` / `useNavigate` and route paths (`/`, `/funds`, `/investors`, `/calls`, `/distributions`, `/documents`, `/letters`, `/tasks`, `/notifications`) instead of the prototype's `Route` enum
  - Create `frontend/src/layouts/AppShell.tsx` (a new sibling of `MainLayout.tsx`) that renders `<div className="flex min-h-svh bg-page text-ink-900">` with `<Sidebar />` and `<main>{<Outlet />}</main>` — model on `edenscale/src/App.tsx`
  - Create `frontend/src/pages/DashboardPage.tsx` that mirrors the prototype's page structure (eyebrow, display title, stat cards, recent funds list, upcoming capital calls list) but reads data via `useQuery({ queryKey: ["dashboard","overview"], queryFn: () => api.GET("/dashboard/overview") })` from `@/lib/api`. Keep the empty-state UI pleasant when arrays are empty
  - Update `frontend/src/App.tsx` so the protected app routes (`/`, etc.) render inside `AppShell` and the `/` route renders the new `DashboardPage`. Keep `/login` standalone as it is today
  - Do NOT port the other 9 prototype pages yet — leave the sidebar links present but pointing at routes that will be filled in later phases (a `<Route path="/funds" element={<ComingSoon page="Funds" />} />` placeholder is fine; create one tiny `ComingSoon.tsx` shared component)

- [ ] Verify the full stack runs and quality gates pass:
  - From `backend/`, run `uv run pytest -v` and confirm tests pass (fix any test that broke from User model changes by adjusting the test fixtures, not by reverting the model changes)
  - From the repo root, run `make lint` and resolve any ruff / ty / black / isort findings introduced by the new code
  - From the repo root, run `make openapi` once more to confirm the schema is still in sync after lint fixes
  - Start the backend (`make start-backend`) in one shell and the frontend (`make start-frontend`) in another, open `http://localhost:3000`, log in via Hanko, and confirm the Dashboard loads with the EdenScale typography (Cormorant Garamond display + Inter Tight body) and parchment background, with stats rendered (zeros are acceptable on an empty DB). Capture any runtime errors and fix them before declaring the phase done
