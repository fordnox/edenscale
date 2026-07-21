---
type: reference
title: System Overview
created: 2026-04-29
tags:
  - architecture
  - fastapi
  - react
related:
  - '[[API-Layering]]'
  - '[[Database-Schema]]'
  - '[[Frontend-Routing]]'
  - '[[RBAC-Model]]'
  - '[[ADR-001-RBAC-Via-Hanko-JWT]]'
  - '[[ADR-002-Storage-Port-Pattern]]'
  - '[[ADR-003-Per-Org-Membership-Roles]]'
---

# System Overview

EdenScale is a two-service monorepo wired together through a generated OpenAPI client. It is the operational backbone for a private fund manager working with limited partners — funds, commitments, capital calls, distributions, documents, and letters all live behind a single authenticated React app.

## Topology

```
┌──────────────────────┐    Hanko cookie/JWT     ┌──────────────────────┐
│  React + Vite SPA    │ ──────────────────────▶│  Hanko Cloud         │
│  frontend/ (Node 20) │ ◀──────── JWT ─────────│  (passkey/email IdP) │
└──────────┬───────────┘                         └──────────────────────┘
           │ Bearer JWT
           ▼
┌──────────────────────┐                         ┌──────────────────────┐
│  FastAPI service     │ ──── arq enqueue ─────▶│  Redis (queue)       │
│  backend/ (Py 3.12)  │                         │  + arq worker        │
└──────────┬───────────┘                         └──────────────────────┘
           │ SQLAlchemy
           ▼
┌──────────────────────┐
│  PostgreSQL          │
│  (required in dev too;│
│   no SQLite fallback) │
└──────────────────────┘
```

> **2026-07-22 correction:** the diagram above used to say "SQLite in dev".
> That is no longer true — `app/core/config.py::Settings._require_postgresql_dsn`
> is a `model_validator` that raises at startup if `APP_DATABASE_DSN` doesn't
> start with `postgresql`; `app/core/database.py` has no SQLite branch.
> PostgreSQL is required in every environment, local dev included.

- **Frontend:** React + Vite + TypeScript, Tailwind CSS v4, React Router, TanStack Query, and Radix/shadcn-style primitives. Turborepo orchestrates `apps/manager`, `apps/investor`, `apps/web`, `apps/gateway`, `apps/emails`, and shared packages under `packages/`.
- **Backend:** FastAPI on Python 3.12, SQLAlchemy ORM, Alembic migrations, `pydantic-settings` config. Single `FastAPI()` instance in `backend/app/main.py`; tenant routers are mounted under `/dashboard`, `/users`, `/funds`, `/investors`, `/commitments`, `/capital-calls`, `/distributions`, `/documents`, `/communications`, `/tasks`, `/notifications`, `/audit-logs`, and `/organizations`; platform administration is isolated under `/superadmin`.
- **Background jobs:** `arq` worker (`app.worker.WorkerSettings`) on a Redis queue named after `settings.APP_DOMAIN`. Enqueue via `app.tasks.enqueue_task` which opens and closes a fresh pool per call.
- **Storage:** Documents go through a [`StoragePort`](../../backend/app/services/storage.py) abstraction; the shipped default is `LocalDevStorage` writing to `backend/dev_storage/`. See [[ADR-002-Storage-Port-Pattern]].

## OpenAPI as the contract

The OpenAPI schema is the single source of truth for the API surface. The dev loop is:

1. Backend route or schema changes → run `make openapi`.
2. `make openapi` regenerates `apps/backend/openapi.json` and runs `pnpm turbo run generate-client --filter=@edenscale/api` to refresh `packages/api/src/schema.d.ts`.
3. Frontend code uses `openapi-fetch` against those generated types via `@edenscale/api`. There are no hand-written request/response types.

A frontend type error after a backend change almost always means `make openapi` was skipped. See the README's pre-commit checklist (test, lint, openapi-sync).

Dashboard monetary aggregates are returned as currency-grouped `{currency_code, amount}` collections. Neither the API nor a frontend may add amounts from different currencies or relabel a mixed-currency total as USD.

## Authentication and authorisation

Authentication is delegated to Hanko (passkey + email magic link). The backend never sees credentials — it validates the Hanko-issued RS256 JWT against `{HANKO_API_URL}/.well-known/jwks.json` and pulls the subject claim, then maps it to a local `users` row keyed on `hanko_subject_id`.

Authorisation is layered locally, and — as of the ADR-003 migration — is **per-organization**, not global. `users` has no `role` column and no `organization_id` column; roles live on `user_organization_memberships`, and which organization a request acts on travels on the `X-Organization-Id` header (see [[RBAC-Model]] for verification detail):

- `get_current_user` (in `app/core/auth.py`) — JWT validity, then resolves/auto-provisions the local `User` row. New users get **no** default role — access comes only from membership rows (created via invitation acceptance) or from being listed in `SUPERADMIN_EMAIL`.
- `get_active_membership` (in `app/core/rbac.py`) — resolves the `UserOrganizationMembership` for the caller + the `X-Organization-Id` header. This step is what makes a request's data access explicit; omitting it (e.g. hand-rolling a query filtered only by `Fund.organization_id` from some other source) is exactly how an unscoped cross-tenant query would slip in.
- `require_membership_roles(...)` — dependency factory that 403s when the *active membership's* role is not in the allow-list. (`require_roles` does not exist.)
- Repository-level scoping — `list_for_membership` / `membership_can_view` helpers, keyed on the membership (not the bare user), further filter rows by `membership.organization_id` (admin/fund_manager) or by the user's `investor_contacts` link intersected with `membership.organization_id` (LPs, via `app/repositories/lp_scope.py`).
- Superadmin is separate from all of the above: config-defined via `SUPERADMIN_EMAIL`, never a membership row, and confined to `/superadmin/*` routes — `get_active_membership` explicitly rejects superadmins.

For the full role rules and examples, see [[RBAC-Model]]. For the Hanko + local-user join trade-off, see [[ADR-001-RBAC-Via-Hanko-JWT]]. For why roles moved off `users` onto membership rows, see [[ADR-003-Per-Org-Membership-Roles]].

## Where to look next

| Question                                            | Document                |
| --------------------------------------------------- | ----------------------- |
| How is a request handled end-to-end?                | [[API-Layering]]        |
| What tables exist and how are they related?         | [[Database-Schema]]     |
| Who can see what?                                   | [[RBAC-Model]]          |
| What's the route map on the SPA?                    | [[Frontend-Routing]]    |
| Why is there a local User row at all?               | [[ADR-001-RBAC-Via-Hanko-JWT]] |
| Why does `Document.file_url` round-trip via a port? | [[ADR-002-Storage-Port-Pattern]] |
