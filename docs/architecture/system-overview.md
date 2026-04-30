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
│  (SQLite in dev)     │
└──────────────────────┘
```

- **Frontend:** React 18 + Vite 7 + TypeScript, Tailwind CSS v4, React Router v6, TanStack Query, Radix UI primitives in `frontend/src/components/ui/`.
- **Backend:** FastAPI on Python 3.12, SQLAlchemy ORM, Alembic migrations, `pydantic-settings` config. Single `FastAPI()` instance in `backend/app/main.py`; routers mounted under `/dashboard`, `/users`, `/funds`, `/investors`, `/commitments`, `/capital-calls`, `/distributions`, `/documents`, `/communications`, `/tasks`, `/notifications`, `/audit-logs`, `/organizations`.
- **Background jobs:** `arq` worker (`app.worker.WorkerSettings`) on a Redis queue named after `settings.APP_DOMAIN`. Enqueue via `app.tasks.enqueue_task` which opens and closes a fresh pool per call.
- **Storage:** Documents go through a [`StoragePort`](../../backend/app/services/storage.py) abstraction; the shipped default is `LocalDevStorage` writing to `backend/dev_storage/`. See [[ADR-002-Storage-Port-Pattern]].

## OpenAPI as the contract

The OpenAPI schema is the single source of truth for the API surface. The dev loop is:

1. Backend route or schema changes → run `make openapi`.
2. `make openapi` regenerates `backend/openapi.json` and runs `pnpm run generate-client` to refresh `frontend/src/lib/schema.d.ts`.
3. Frontend code uses `openapi-fetch` against those generated types via `frontend/src/lib/api.ts`. There are no hand-written request/response types.

A frontend type error after a backend change almost always means `make openapi` was skipped. See the README's pre-commit checklist (test, lint, openapi-sync).

## Authentication and authorisation

Authentication is delegated to Hanko (passkey + email magic link). The backend never sees credentials — it validates the Hanko-issued RS256 JWT against `{HANKO_API_URL}/.well-known/jwks.json` and pulls the subject claim, then maps it to a local `users` row keyed on `hanko_subject_id`.

Authorisation is layered locally:

- `get_current_user` (in `app/core/auth.py`) — JWT validity only.
- `get_current_user_record` (in `app/core/rbac.py`) — find-or-create local `User`, default new users to `UserRole.lp`.
- `require_roles(...)` — dependency factory that 403s when the resolved role is not in the allow-list.
- Repository-level scoping — `list_for_user` style helpers further filter rows by `organization_id` (fund_managers) or by the user's `investor_contacts` link (LPs).

For the full role rules and examples, see [[RBAC-Model]]. For the Hanko + local-user join trade-off, see [[ADR-001-RBAC-Via-Hanko-JWT]].

## Where to look next

| Question                                            | Document                |
| --------------------------------------------------- | ----------------------- |
| How is a request handled end-to-end?                | [[API-Layering]]        |
| What tables exist and how are they related?         | [[Database-Schema]]     |
| Who can see what?                                   | [[RBAC-Model]]          |
| What's the route map on the SPA?                    | [[Frontend-Routing]]    |
| Why is there a local User row at all?               | [[ADR-001-RBAC-Via-Hanko-JWT]] |
| Why does `Document.file_url` round-trip via a port? | [[ADR-002-Storage-Port-Pattern]] |
