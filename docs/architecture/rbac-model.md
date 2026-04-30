---
type: reference
title: RBAC Model
created: 2026-04-29
tags:
  - architecture
  - auth
  - rbac
related:
  - '[[System-Overview]]'
  - '[[API-Layering]]'
  - '[[Database-Schema]]'
  - '[[ADR-001-RBAC-Via-Hanko-JWT]]'
---

# RBAC Model

EdenScale has three roles. Authentication is delegated to Hanko; authorisation is local. The role lives on `users.role` (enum `user_role`) and is read once per request via `get_current_user_record`. See [[ADR-001-RBAC-Via-Hanko-JWT]] for why the role lives in our DB rather than in Hanko custom claims.

## Roles

| Role           | Description                                                                            |
| -------------- | -------------------------------------------------------------------------------------- |
| `admin`        | Platform administrator. Sees every organization. Only role that can change another user's `role`. |
| `fund_manager` | Operator at a fund_manager_firm. Sees and writes within their own `organization_id`.   |
| `lp`           | Limited partner. Sees only the funds, commitments, calls, distributions, documents, and letters that touch the investors they are a contact for. |

New users are auto-provisioned on first JWT sight with `role = lp` (in `app/core/rbac.py::get_current_user_record`). Promotion to `fund_manager` or `admin` is an admin-only operation via `PATCH /users/{id}/role`.

## The dependency stack

```
Request
  └─▶ HTTPBearer ──▶ get_current_user (JWT validity, claims dict)
                         └─▶ get_current_user_record (local User row)
                               └─▶ require_roles(*allowed) (per-route gate)
```

- `get_current_user` (`app/core/auth.py`) — RS256 verify against Hanko JWKS, audience = `HANKO_AUDIENCE`. Returns the decoded payload.
- `get_current_user_record` (`app/core/rbac.py`) — find-or-create the local `User` keyed on `hanko_subject_id`. Stashes `user_id` into `AuditContextMiddleware`'s `ContextVar` so audit-log listeners know who did the write.
- `require_roles(*allowed)` (`app/core/rbac.py`) — dependency factory. 403s when `current_user.role not in allowed`.

```python
from app.core.rbac import require_roles
from app.models.enums import UserRole

@router.post("/", dependencies=[Depends(require_roles(UserRole.admin, UserRole.fund_manager))])
async def create_fund(...): ...
```

Routers under `/dashboard` and `/users` are gated by `Depends(get_current_user)` at the `include_router` level in `app/main.py` — individual routes don't re-declare auth. Stricter role gates are layered on per-route as needed.

## Two enforcement layers

RBAC happens in **two** places, on purpose:

1. **Route-level deny** with `require_roles(...)` — blunt: "only admin / fund_manager may call this endpoint at all". Used for write endpoints that LPs should never touch (creating funds, editing organizations, posting payments).

2. **Repository-level scope** with `list_for_user` / `user_can_view` — fine-grained: "this LP only sees the four funds they have commitments in". Used for any list or detail endpoint where multiple roles are allowed but they each see a different slice. The pattern lives in `app/repositories/fund_repository.py::list_for_user` and is mirrored across `investor_repository`, `commitment_repository`, `capital_call_repository`, `distribution_repository`, `document_repository`, and `communication_repository`.

If you only have one of the two, you have a bug:

- Skip the route-level gate and an LP can call a write endpoint they should not be able to reach.
- Skip the repository scope and a fund_manager can read another firm's data via the list endpoint.

## Visibility rules per entity

| Entity              | admin    | fund_manager                        | lp                                                                  |
| ------------------- | -------- | ----------------------------------- | ------------------------------------------------------------------- |
| `organizations`     | All      | Own org only                        | Own org only (read)                                                 |
| `users`             | All      | Own org only                        | Self only (`/users/me`)                                             |
| `fund_groups`       | All      | Own org only                        | Hidden                                                              |
| `funds`             | All      | Own org only                        | Funds where they're a contact on a committed investor               |
| `fund_team_members` | All      | Own org's funds                     | Hidden                                                              |
| `investors`         | All      | Own org only                        | Investors where they're a contact                                   |
| `investor_contacts` | All      | Own org only                        | Self-row only                                                       |
| `commitments`       | All      | Own org's funds                     | Their investor's commitments                                        |
| `capital_calls`     | All      | Own org's funds (write)             | Calls on their commitments (read-only)                              |
| `distributions`     | All      | Own org's funds (write)             | Distributions on their commitments (read-only)                      |
| `documents`         | All      | Own org's docs                      | Docs scoped to a fund/investor they have access to (and not `is_confidential` they aren't a recipient of) |
| `communications`    | All      | Own org's funds (write)             | Letters where they're a recipient                                   |
| `tasks`             | All      | Own org / assigned to them          | Hidden (LPs do not have task management)                            |
| `notifications`     | Self     | Self                                | Self                                                                |
| `audit_logs`        | All      | Hidden                              | Hidden                                                              |

LP visibility follows the chain: `users → investor_contacts → investors → commitments → fund`. The query template lives in `FundRepository.list_for_user`:

```python
visible_fund_ids = (
    select(Commitment.fund_id)
    .join(InvestorContact,
          InvestorContact.investor_id == Commitment.investor_id)
    .where(InvestorContact.user_id == user.id)
)
```

## Frontend gating

Authorisation is **enforced** on the backend; the frontend uses role only to hide UI a user can't act on. Two helpers:

- **`useNavItems()`** (`frontend/src/hooks/useNavItems.ts`) — reads `GET /users/me` once (TanStack Query, 5-min stale time) and returns the sidebar entries the role should see. LPs get a stripped sidebar (no Capital Calls, Distributions, Tasks). Admins get the full set plus an Audit Log entry.
- **`<RequireRole allowed={[...]}>`** (`frontend/src/components/RequireRole.tsx`) — wraps a page; renders an empty-state with a "Back to dashboard" link when the role does not match. Used by `OrganizationSettingsPage` (admin + fund_manager) and `AuditLogPage` (admin only).

Hiding nav items is a UX nicety; the API always re-checks. If you add a new role-gated page, gate it on **both** sides.

## Tests

Each role × entity matrix cell has at least one route-level test. Run `make test` (currently 145 passing) and grep for `as_role(` / `assume_role(` test helpers to see the pattern. New endpoints **must** include role tests covering the three roles.
