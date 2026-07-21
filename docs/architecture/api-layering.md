---
type: reference
title: API Layering
created: 2026-04-29
tags:
  - architecture
  - fastapi
  - backend
related:
  - '[[System-Overview]]'
  - '[[Database-Schema]]'
  - '[[RBAC-Model]]'
---

# API Layering

> **2026-07-22 correction.** The RBAC-related claims in this file (a
> `require_roles(...)` gate, `list_for_user` repository helpers keyed on a
> global `user.role`) described the pre-membership model. Corrected below
> against current code; see [[RBAC-Model]] and
> [[ADR-003-Per-Org-Membership-Roles]] for the full picture.

The backend is a thin onion. A request flows **router → repository → model**, with `schemas/` (Pydantic) defining the request/response contract that crosses each layer. Business logic lives in repositories and services, never in route handlers.

```
HTTP request (Bearer JWT + X-Organization-Id)
    │
    ▼
┌──────────────────────────────────────────────┐
│ routers/<entity>.py                          │  HTTP shape, deps,
│   • Pydantic body / query parsing            │  RBAC gates, error
│   • Depends(get_db, get_active_membership)   │  mapping
│   • require_membership_roles(...)            │
└────────────────────┬─────────────────────────┘
                     │ calls
                     ▼
┌──────────────────────────────────────────────┐
│ repositories/<entity>_repository.py          │  Domain logic +
│   • SQLAlchemy queries / scoping             │  visibility rules,
│   • list_for_membership / membership_can_view│  pro-rata math, etc.
│   • Status transitions, allocation math      │
└────────────────────┬─────────────────────────┘
                     │ persists
                     ▼
┌──────────────────────────────────────────────┐
│ models/<entity>.py                           │  ORM mapping,
│   • SQLAlchemy declarative                   │  table relationships,
│   • Enum columns from models/enums.py        │  audit listeners
└──────────────────────────────────────────────┘
```

## Layers in detail

### `routers/`

One module per top-level resource (`backend/app/routers/funds.py`, `investors.py`, `capital_calls.py`, …). Each module exposes an `APIRouter` instance — declared with `APIRouter(dependencies=[Depends(get_current_user)])` in the router file itself, not passed to `include_router` in `main.py` (verified: `app/main.py` has no `dependencies=` argument on any `include_router` call) — and is mounted in [`backend/app/main.py`](../../backend/app/main.py). Routers:

- Take the DB session via `Depends(get_db)`. Org-scoped routes take the active membership via `Depends(get_active_membership)` (resolved from the `X-Organization-Id` header); routes that aren't org-scoped (e.g. `/users/me`, `/notifications`) take the local user via `Depends(get_current_user_record)` instead.
- Apply role gates with `Depends(require_membership_roles(UserRole.admin, UserRole.fund_manager))` when an action should be denied to LPs outright. There is no `require_roles` — it does not exist in this codebase; see [[RBAC-Model]].
- Return Pydantic `*Read` / `*ListItem` models declared in `schemas/`.
- Map `None` returns from repositories to `404`s and other domain errors to `400`/`409`/`422`.

Routers do **not** issue raw SQL or instantiate ORM models directly. They receive request bodies as Pydantic models and pass them straight into a repository method.

### `repositories/`

One repository class per entity. They own:

- The **scope query** (`_base_query`) and the **role-aware list**, named `list_for_membership` (not `list_for_user`) across every entity repository — verified in `fund_repository.py`, `investor_repository.py`, `commitment_repository.py`, `capital_call_repository.py`, `distribution_repository.py`, `document_repository.py`, `communication_repository.py`, `task_repository.py`, `fund_group_repository.py`, `audit_log_repository.py`. Each takes a `UserOrganizationMembership`, not a `User`, so the scope is always relative to the org the caller is currently acting through. Detail visibility uses the matching `membership_can_view(membership, row)`.
- **State transitions** — capital-call lifecycle, distribution payment posting, commitment status changes.
- **Pro-rata allocation** — `services/allocation.py` is called from the capital-call and distribution repositories.
- **Cross-entity invariants** — e.g. updating `commitments.called_amount` when a capital-call item is paid.

A repository method returns ORM rows or domain dataclasses; routers serialise them into Pydantic `*Read` models.

### `models/`

SQLAlchemy declarative models, one per table, plus `enums.py` mirroring the dbml enums verbatim. Models declare relationships and unique constraints; they do **not** contain business logic. ORM-level `after_insert` / `after_update` / `after_delete` listeners in `app/core/audit.py` fan out to `audit_logs` for the registered entities — see [[Database-Schema]] for the audit fan-out shape.

### `schemas/`

Pydantic v2 models. Conventions:

- `XCreate` — request body for `POST`.
- `XUpdate` — request body for `PATCH`, all fields `Optional`.
- `XRead` — full read DTO returned for single-entity GETs and after writes.
- `XListItem` — slimmer DTO returned for list endpoints.
- `XOverview` / `XStats` — denormalised aggregates for dashboard cards.

These DTOs are the source of truth for the OpenAPI schema and therefore for the generated frontend types in `packages/api/src/schema.d.ts`.

## Concrete example: list funds

```python
# routers/funds.py
@router.get("", response_model=list[FundListItem])
def list_funds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = FundRepository(db)
    rows = repo.list_for_membership(membership, skip=skip, limit=limit)
    return [_to_list_item(fund, current_size) for fund, current_size in rows]
```

```python
# repositories/fund_repository.py
_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager)

def list_for_membership(self, membership, skip=0, limit=100):
    query = self._base_query().filter(Fund.organization_id == membership.organization_id)
    if membership.role not in _ORG_VISIBLE_ROLES:
        visible_fund_ids = select(Commitment.fund_id).where(
            Commitment.investor_id.in_(lp_visible_investor_ids(membership))
        )
        query = query.filter(Fund.id.in_(visible_fund_ids))
    return query.order_by(Fund.created_at, Fund.id).offset(skip).limit(limit).all()
```

The router knows nothing about commitments or investor contacts. The repository does. The scope is always anchored on `membership.organization_id` — there is no `user.organization_id` to fall back on. The schema (`FundListItem`) is what the frontend consumes via the generated client.

## Cross-cutting infrastructure

- **`core/auth.py`** — Hanko JWT validation; resolves the local `User` row.
- **`core/rbac.py`** — `get_current_user_record`, `get_active_membership`, `require_membership_roles`, `require_superadmin`, `require_tenant_user`. See [[RBAC-Model]].
- **`core/database.py`** — engine + `get_db` session dependency.
- **`core/audit.py`** + **`middleware/audit_context.py`** — populates `audit_logs`. The middleware stashes actor + IP in a `ContextVar`; SQLAlchemy listeners read it.
- **`services/storage.py`** — `StoragePort` abstraction for documents. See [[ADR-002-Storage-Port-Pattern]].
- **`services/notifications.py`** — fan-out helper (`notify_<event>()`) that creates `notifications` rows on domain events and dispatches to channels in `services/channels/`. (Corrected: the file is `notifications.py`, not `notification_service.py`.)
- **`tasks.py`** + **`worker.py`** — arq enqueue helpers and the worker `WorkerSettings` registration.

## Pre-commit pipeline

After any backend change to a route or schema:

1. `make test` — pytest must pass.
2. `make lint` — import smoke test, `ruff`, `ty`, `black`, `isort`.
3. `make openapi` — regenerate `apps/backend/openapi.json` and `packages/api/src/schema.d.ts`.

Skipping step 3 will fail the frontend type check on the next pull.
