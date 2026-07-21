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
  - '[[ADR-003-Per-Org-Membership-Roles]]'
---

# RBAC Model

> **2026-07-22 rewrite.** This file previously described the ADR-001 shape
> (a single `role` + `organization_id` on `users`). That shape was replaced
> by per-organization membership rows; see
> [[ADR-003-Per-Org-Membership-Roles]] for the full narrative and the code
> citations backing every claim below. This rewrite verifies each claim
> directly against `apps/backend/app` as of 2026-07-22 rather than
> re-deriving ADR-003's reasoning.

Authentication is delegated to Hanko; authorisation is local. **There is no
role on `users`.** `apps/backend/app/models/user.py` has no `role` column and
no `organization_id` column — it exposes a `memberships` relationship to
`UserOrganizationMembership` and a computed `is_superadmin` property. Roles
live on the membership row: `(user_id, organization_id, role)`, so the same
person can be `admin` in one organization and `lp` in another. Which
organization a request acts on is **not** implicit on the user — it travels
on the `X-Organization-Id` request header (see "The dependency stack"
below). See [[ADR-001-RBAC-Via-Hanko-JWT]] for why authorisation state lives
in our DB at all rather than in Hanko custom claims (that reasoning still
holds); see [[ADR-003-Per-Org-Membership-Roles]] for why it moved off `users`
onto membership rows.

## Roles

`UserRole` (`app/models/enums.py`) has four values: `superadmin`, `admin`,
`fund_manager`, `lp`. Only three of them can ever be a *membership* role —
`superadmin` is rejected as an invitation/membership role
(`app/schemas/organization_invitation.py`) and is used only for labeling
elsewhere. Superadmin status itself is never a membership row; see below.

| Role           | Description                                                                            |
| -------------- | -------------------------------------------------------------------------------------- |
| `admin`        | Membership role. Full read/write within the organizations they're a member of, plus the only role that can change another member's role (`PATCH /users/{id}/role`, gated `require_membership_roles(UserRole.admin)`). Verified: across every entity router checked (funds, investors, commitments, capital-calls, distributions, documents, communications, tasks, fund-groups), `admin` and `fund_manager` are granted identical read/write access via a shared `_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager)` constant — `admin` has no broader *data* visibility than `fund_manager`, only the extra member/role-management endpoints. |
| `fund_manager` | Membership role. Operator at a `fund_manager_firm`. Sees and writes within the **active organization** (resolved from `X-Organization-Id`, not a column on `users`). |
| `lp`           | Membership role. Limited partner. Sees only the funds, commitments, calls, distributions, documents, and letters that touch the investors they are a linked contact for (via `investor_contacts`), scoped to the active membership's organization. |
| `superadmin`   | **Not a membership role — config-defined.** `User.is_superadmin` is a property that checks the caller's (Hanko-verified) email against `settings.superadmin_emails` (parsed from `SUPERADMIN_EMAIL`). No database row, by itself, grants it. See "Superadmin isolation" below. |

New users are auto-provisioned on first JWT sight with **no role at all**
(`UserRepository.get_or_provision_by_hanko_id`, called from
`get_current_user`) — access comes later, purely from whatever membership
rows exist for them (created by accepting an org invitation) or from being
listed in `SUPERADMIN_EMAIL`. There is no default role comparable to the old
"auto-provision as `lp`".

`PATCH /users/{id}/role` **does exist** (`app/routers/users.py`), contrary
to what an earlier version of this doc implied was removed — but it changes
the *target's membership row in the caller's active organization*, not a
global role. It requires the caller's active membership to be `admin`
(`require_membership_roles(UserRole.admin)`), 404s if the target has no
membership in that org, and returns `OrgMemberRead` (the target's org-scoped
role). It cannot grant `superadmin` — the schema (`UserRoleUpdate`) accepts
any `UserRole` value, but nothing in the codebase assigns
`role="superadmin"` to a membership row in the normal flow (see ADR-003 on
this being tracked as a "vestigial enum member" wart, not currently
enforced by validation on this specific endpoint).

## The dependency stack

```
Request (Bearer JWT + X-Organization-Id header)
  └─▶ HTTPBearer ──▶ get_current_user (JWT validity, local User row)
                         └─▶ get_current_user_record (audit-log actor)
                               └─▶ get_active_membership (resolves membership from X-Organization-Id)
                                     └─▶ require_membership_roles(*allowed) (per-route gate, optional)
```

- `get_current_user` (`app/core/auth.py`) — RS256 verify against Hanko JWKS,
  audience = `HANKO_AUDIENCE`. Despite the name, it does **not** return the
  raw JWT payload dict — it resolves (find-or-provision) the local `User`
  row via `UserRepository.get_or_provision_by_hanko_id` and returns that.
- `get_current_user_record` (`app/core/rbac.py`) — thin pass-through that
  records the resolved user for audit logging (`set_audit_user`) and returns
  it. Used directly (without a membership) by routes that aren't
  org-scoped, e.g. `/users/me`, `/notifications`.
- `get_active_membership` (`app/core/rbac.py`) — resolves the
  `UserOrganizationMembership` the caller is acting through:
  - `X-Organization-Id` header present → look up that
    `(user_id, organization_id)` membership row, or 403 "Not a member of
    this organization".
  - Header absent → use the caller's sole membership if they have exactly
    one; 400 "X-Organization-Id required" if they have zero or several.
  - **Superadmins are rejected here even if a matching membership row
    exists** — the superadmin surface never impersonates a tenant
    membership (see below).
- `require_membership_roles(*allowed)` (`app/core/rbac.py`) — dependency
  factory built on top of `get_active_membership`. 403s when
  `membership.role not in allowed`. This is the replacement for the old
  (now nonexistent) `require_roles(*allowed)` — **`require_roles` does not
  exist anywhere in `apps/backend/app`**; grep confirms zero hits.

```python
from app.core.rbac import require_membership_roles
from app.models.enums import UserRole
from app.models.user_organization_membership import UserOrganizationMembership

@router.post(
    "/",
    dependencies=[Depends(require_membership_roles(UserRole.admin, UserRole.fund_manager))],
)
async def create_fund(
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
    ...
): ...
```

Auth is declared **per-router**, not at the `include_router` level:
`app/main.py` mounts every router with no `dependencies=` argument; each
router file instead does `APIRouter(dependencies=[Depends(get_current_user)])`
itself (verified: `app/main.py` has zero `dependencies=[Depends(...)]`
occurrences on any `include_router` call). Stricter gates
(`get_active_membership`, `require_membership_roles`, `require_superadmin`)
are layered on per-route on top of that base JWT check.

## Superadmin isolation

Superadmin is a configuration-defined platform identity, not a tenant
membership role. Platform operations live exclusively under `/superadmin/*`
(`app/routers/superadmin.py`) and use `require_superadmin`; they never use
`X-Organization-Id`. Conversely, `get_active_membership` rejects superadmins
even if a matching persisted membership exists — so **a superadmin cannot
call any of the regular tenant-scoped entity routes** (funds, investors,
commitments, capital-calls, distributions, documents, communications,
tasks) at all, membership or not; their entire surface is the
`organizations` / `users` / `memberships` management endpoints under
`/superadmin`. This is a meaningfully narrower surface than "sees
everything" — see the corrected visibility table below.

## Two enforcement layers

RBAC happens in **two** places, on purpose:

1. **Route-level deny** with `require_membership_roles(...)` — blunt: "only
   `admin` / `fund_manager` may call this endpoint at all". Used for write
   endpoints LPs should never touch (creating funds, editing organizations,
   posting payments).
2. **Repository-level scope** with `list_for_membership` /
   `membership_can_view` — fine-grained: "this LP only sees the four funds
   they have commitments in". Verified present, with that exact naming
   pattern, in `fund_repository.py`, `investor_repository.py`,
   `commitment_repository.py`, `capital_call_repository.py`,
   `distribution_repository.py`, `document_repository.py`,
   `communication_repository.py`, `task_repository.py`,
   `fund_group_repository.py`, and `audit_log_repository.py`. (The older
   `list_for_user` / `user_can_view` naming this doc previously cited does
   not exist for these entities — `list_for_user` survives only on
   `UserOrganizationMembershipRepository`, `NotificationRepository`, and
   `InvestorContactRepository.list_for_user_and_investor`, none of which are
   role-scoped the same way.)

If you only have one of the two, you have a bug:

- Skip the route-level gate and an LP can call a write endpoint they should
  not be able to reach.
- Skip the repository scope and a member can read another org's data — or,
  now that roles are per-org, a user who is `lp` in Org A but also holds
  `fund_manager` in Org B could see Org A data if a repository scoped by
  role instead of by the **active membership's `organization_id`**. This is
  precisely why every scope helper takes a `membership` argument rather
  than a bare `role` — the active membership carries both.

## Visibility rules per entity

**Rewritten 2026-07-22** after checking every listed repository's role gate
directly (previous version was carried over from the ADR-001 model and
listed "admin: All" for entities `admin` in the new model cannot reach —
see "Superadmin isolation" above). Within an organization, `admin` and
`fund_manager` are visibility-equivalent for all of these entities (see the
`_ORG_VISIBLE_ROLES` note above); `admin`'s extra power is member/role
management, not wider data access. Superadmin cannot reach any of these
entity endpoints at all (no route accepts a superadmin without an active
membership, and `get_active_membership` explicitly rejects superadmins).

| Entity               | admin / fund_manager (active org)                     | lp (active org)                                                        | superadmin                     |
| -------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------- |
| `organizations`      | Own org (via `get_active_membership`)                   | Own org (read)                                                           | All, via `/superadmin/*` only   |
| `users`               | Own org's members (`GET /users`); `admin` can change a member's org role | Self only (`/users/me`)                                    | All, via `/superadmin/*` only   |
| `fund_groups`        | Own org                                                  | Fund groups reachable through a fund they hold a commitment in (**not** hidden) | Not reachable via this route    |
| `funds`               | Own org                                                  | Funds where they're a contact on a committed investor                    | Not reachable via this route    |
| `investors`           | Own org                                                  | Investors where they're a contact                                        | Not reachable via this route    |
| `investor_contacts`  | Own org                                                  | Self-row only                                                            | Not reachable via this route    |
| `commitments`         | Own org's funds                                          | Their investor's commitments                                             | Not reachable via this route    |
| `capital_calls`       | Own org's funds (write)                                  | Calls on their commitments (read-only)                                   | Not reachable via this route    |
| `distributions`       | Own org's funds (write)                                  | Distributions on their commitments (read-only)                           | Not reachable via this route    |
| `documents`            | Own org's docs                                           | Docs scoped to an investor they're a contact for, plus non-confidential docs on a fund they hold a commitment in | Not reachable via this route |
| `communications`      | Own org's funds (write)                                  | Letters where they're a recipient, or ones they sent                     | Not reachable via this route    |
| `tasks`                | Own org / assigned or created by them                    | **Not hidden** — tasks assigned to them (can view/complete, cannot edit metadata) | Not reachable via this route |
| `notifications`       | Self                                                     | Self                                                                      | Self (this one route works for any authenticated user, superadmin included, since it never touches `get_active_membership`) |
| `audit_logs`          | Every event in the org                                   | Only events they personally caused                                       | Not reachable via this route    |

> `fund_team_members` was in an earlier version of this table; the table and
> model were dropped (`app/alembic/versions/..._drop_fund_team_members.py`)
> and no longer exist — removed from this table rather than left stale.

LP visibility follows the chain `users → investor_contacts → investors →
commitments → fund`, further intersected with the active membership's
`organization_id` (`app/repositories/lp_scope.py::lp_visible_investor_ids`):

```python
def lp_visible_investor_ids(membership: UserOrganizationMembership) -> Select:
    return (
        select(InvestorContact.investor_id)
        .join(Investor, Investor.id == InvestorContact.investor_id)
        .where(
            InvestorContact.user_id == membership.user_id,
            Investor.organization_id == membership.organization_id,
        )
    )
```

## Frontend gating

Authorisation is **enforced** on the backend; the frontend uses the active
membership's role only to hide UI a user can't act on. It reads
`activeMembership.role` (verified in
`apps/manager/src/components/RequireRole.tsx` and
`apps/manager/src/hooks/useNavItems.ts` — both key off
`useActiveOrganization().activeMembership?.role`, **not** a global user
role, since there isn't one):

- **Manager nav/guards** (`apps/manager/src/hooks/useNavItems.ts`,
  `apps/manager/src/components/RequireRole.tsx`) — expose
  admin/fund-manager workflows and gate manager-only pages.
- **Investor nav** (`apps/investor/src/hooks/useNavItems.ts`) — exposes only
  LP-facing read-only sections.

Hiding nav items is a UX nicety; the API always re-checks. If you add a new
role-gated page, gate it on **both** sides, and remember the gate is keyed
on the *active membership*, not a global role — a page has to react to org
switches.

## Tests

`cd apps/backend && uv run pytest -q` (472 passing as of 2026-07-22 — expect
this number to drift; don't treat it as a contract). There is no
`as_role(` / `assume_role(` test helper (an earlier version of this doc
claimed there was; grep across `apps/backend/tests` found zero matches).
Tests instead use the `override_user` fixture
(`apps/backend/tests/conftest.py`) to swap `get_current_user`, then create
real `UserOrganizationMembership` rows and send `X-Organization-Id` like a
real client would — there's no shortcut that bypasses the header
resolution.

## Open questions

- Whether `admin`'s ability to change another member's role
  (`PATCH /users/{id}/role`) is meant to be further restricted (e.g. an
  admin demoting the last admin in an org) is not visible from the route
  code alone — not verified either way here.
