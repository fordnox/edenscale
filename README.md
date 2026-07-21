# EdenScale

A fund-administration platform for private-equity fund managers and their
limited partners: commitments, capital calls, distributions, documents,
communications, and (as of the fund-valuation model) NAV / TVPI / RVPI
tracking.

## Topology

One Python/FastAPI backend serves three React SPAs, wired together through a
generated OpenAPI client:

- **`apps/backend`** — FastAPI API (Python 3.12, SQLAlchemy, Pydantic, arq).
- **`apps/manager`**, **`apps/investor`**, **`apps/superadmin`** — React 19 +
  Vite 8 SPAs, mounted under `/manager`, `/investor`, `/superadmin` in
  production.
- **`apps/web`** — Astro marketing site, serves `/`.
- **`apps/docs`** — Astro Starlight docs site, serves `/docs`.
- **`apps/gateway`** — Cloudflare Worker that assembles the built output of
  the above into one asset tree and serves it.
- **`apps/emails`** — React Email templates, pushed to Resend as hosted
  templates.

Shared frontend code lives in `packages/` (`@edenscale/api`, `@edenscale/auth`,
`@edenscale/shared`, `@edenscale/ui`, and brand/config packages). See
`CLAUDE.md` for the full architecture breakdown.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js and [pnpm](https://pnpm.io/)
- Redis (used by the arq background worker; defaults to
  `redis://localhost:6379`)
- **PostgreSQL — required to run the test suite.** `apps/backend/.env.example`
  defaults `APP_DATABASE_DSN` to SQLite, but that default does not work for
  `make test`: on SQLite, roughly 168 of 392 backend tests fail (test
  fixtures pass plain `str` values into `Uuid(as_uuid=True)` columns —
  psycopg2 coerces them under Postgres, SQLite's binder rejects them). This
  is a known gap between the configured default and what actually works, not
  expected/normal behavior. Point `APP_DATABASE_DSN` at a Postgres instance
  before running `make test`. (Whether the *application itself*, as opposed
  to the test suite, runs correctly against the SQLite default has not been
  verified — this README does not make a claim either way.)

## Setup

1. **Install dependencies**: `make sync` (runs `uv sync` in `apps/backend`
   and `pnpm install` for the whole workspace).
2. **Configure environment**: each app that needs one ships a
   `.env.example` — copy it to `.env` in that app's directory before first
   run, at minimum `apps/backend/.env.example`. The backend `.env.example`
   documents `HANKO_API_URL`/`HANKO_API_KEY` (auth), `SUPERADMIN_EMAIL`,
   `STORAGE_BACKEND`, and the Redis/Postgres settings above — set
   `APP_DATABASE_DSN` to a Postgres DSN (see Prerequisites).
3. **Create the database**: `make db-init` creates all tables directly from
   the SQLAlchemy models (fastest for local dev). Alternatively, `make
   upgrade` applies the Alembic migration chain, which matches what
   production does.
4. **Seed demo data** (optional, idempotent): `make db-seed`.
5. **Run it**:
   - `make start-backend` — FastAPI dev server on `localhost:8000`.
   - `make start-manager` / `make start-investor` / `make start-superadmin`
     — the three Vite dev servers, on ports 3000 / 3001 / 3002.
   - `make start-worker` — the arq background worker (notifications,
     scheduled jobs); needs Redis running.

Run `make help` for the full target list.

## Rules before each commit

1. `make test` must pass (`pytest -v` in `apps/backend`).
2. `make lint` must pass (backend import smoke test, `ruff`, `ty`, `black`,
   `isort`).
3. `make openapi` must be run after any backend route/schema change, so
   `apps/backend/openapi.json` and the generated `packages/api` client stay
   in sync.

## Competitors

- Fundrbird
- HC Global
- Carta
- Fundpanel (by Aduro)
- DealCloud
- Affinity
- Juniper Square
