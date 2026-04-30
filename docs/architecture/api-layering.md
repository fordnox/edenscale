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

The backend is a thin onion. A request flows **router → repository → model**, with `schemas/` (Pydantic) defining the request/response contract that crosses each layer. Business logic lives in repositories and services, never in route handlers.

```
HTTP request
    │
    ▼
┌──────────────────────────────────────────────┐
│ routers/<entity>.py                          │  HTTP shape, deps,
│   • Pydantic body / query parsing            │  RBAC gates, error
│   • Depends(get_db, get_current_user_record) │  mapping
│   • require_roles(...)                       │
└────────────────────┬─────────────────────────┘
                     │ calls
                     ▼
┌──────────────────────────────────────────────┐
│ repositories/<entity>_repository.py          │  Domain logic +
│   • SQLAlchemy queries / scoping             │  visibility rules,
│   • list_for_user / user_can_view            │  pro-rata math, etc.
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

One module per top-level resource (`backend/app/routers/funds.py`, `investors.py`, `capital_calls.py`, …). Each module exposes an `APIRouter` instance and is mounted in [`backend/app/main.py`](../../backend/app/main.py). Routers:

- Take the DB session via `Depends(get_db)` and the local user via `Depends(get_current_user_record)`.
- Apply role gates with `Depends(require_roles(UserRole.admin, UserRole.fund_manager))` when an action should be denied to LPs outright.
- Return Pydantic `*Read` / `*ListItem` models declared in `schemas/`.
- Map `None` returns from repositories to `404`s and other domain errors to `400`/`409`/`422`.

Routers do **not** issue raw SQL or instantiate ORM models directly. They receive request bodies as Pydantic models and pass them straight into a repository method.

### `repositories/`

One repository class per entity. They own:

- The **scope query** (`_base_query`) and the **role-aware list** (`list_for_user`) — filter logic is centralised here so a router never has to remember "fund_managers see their org, LPs see their commitments".
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

These DTOs are the source of truth for the OpenAPI schema and therefore for the generated frontend types in `frontend/src/lib/schema.d.ts`.

## Concrete example: list funds

```python
# routers/funds.py
@router.get("", response_model=list[FundListItem])
async def list_funds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_record),
):
    repo = FundRepository(db)
    rows = repo.list_for_user(current_user, skip=skip, limit=limit)
    return [_to_list_item(fund, current_size) for fund, current_size in rows]
```

```python
# repositories/fund_repository.py
def list_for_user(self, user: User, skip=0, limit=100):
    query = self._base_query()
    if user.role is UserRole.admin:
        pass
    elif user.role is UserRole.fund_manager:
        if user.organization_id is None:
            return []
        query = query.filter(Fund.organization_id == user.organization_id)
    else:  # lp
        visible_fund_ids = (
            select(Commitment.fund_id)
            .join(InvestorContact,
                  InvestorContact.investor_id == Commitment.investor_id)
            .where(InvestorContact.user_id == user.id)
        )
        query = query.filter(Fund.id.in_(visible_fund_ids))
    return query.order_by(Fund.id).offset(skip).limit(limit).all()
```

The router knows nothing about commitments or investor contacts. The repository does. The schema (`FundListItem`) is what the frontend consumes via the generated client.

## Cross-cutting infrastructure

- **`core/auth.py`** — Hanko JWT validation.
- **`core/rbac.py`** — `get_current_user_record`, `require_roles`. See [[RBAC-Model]].
- **`core/database.py`** — engine + `get_db` session dependency.
- **`core/audit.py`** + **`middleware/audit_context.py`** — populates `audit_logs`. The middleware stashes actor + IP in a `ContextVar`; SQLAlchemy listeners read it.
- **`services/storage.py`** — `StoragePort` abstraction for documents. See [[ADR-002-Storage-Port-Pattern]].
- **`services/notification_service.py`** — fan-out helper that creates `notifications` rows on domain events.
- **`tasks.py`** + **`worker.py`** — arq enqueue helpers and the worker `WorkerSettings` registration.

## Pre-commit pipeline

After any backend change to a route or schema:

1. `make test` — pytest must pass.
2. `make lint` — import smoke test, `ruff`, `ty`, `black`, `isort`.
3. `make openapi` — regenerate `backend/openapi.json` and `frontend/src/lib/schema.d.ts`.

Skipping step 3 will fail the frontend type check on the next pull.
