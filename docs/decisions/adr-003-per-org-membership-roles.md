---
type: analysis
title: 'ADR-003: Per-organization roles via UserOrganizationMembership'
created: 2026-07-21
tags:
  - auth
  - decision
  - rbac
related:
  - '[[System-Overview]]'
  - '[[RBAC-Model]]'
  - '[[ADR-001-RBAC-Via-Hanko-JWT]]'
  - '[[ADR-002-Storage-Port-Pattern]]'
---

# ADR-003: Per-organization roles via UserOrganizationMembership

**Status:** Accepted (2026-04 / MAESTRO Phase 01–02 and 08)
**Deciders:** Backend team
**Supersedes:** ADR-001 (RBAC via local User row keyed on Hanko subject ID)

## Context

ADR-001 stored `role` and `organization_id` directly on `users` and explicitly
flagged its own limit under "Revisit when": *"We need to support a user
belonging to multiple organizations. Today `users.organization_id` is a
single nullable FK. A many-to-many would require a `user_organizations` table
and reworking every repository scope."*

That is what happened. The build log at
`docs/Auto Run Docs/2026-04-30-Edenscale-2/Phase-01-Membership-Data-Model.md`
records the trigger as: *"This phase lays the data-model foundation for
multi-org membership and global superadmins."* Subsequent phases in the same
directory (`Phase-02-Active-Org-Context.md` through
`Phase-08-Legacy-Cleanup-And-E2E.md`) carried the migration through the
backend, then the frontend, then removed the legacy column
(`995610d4 refactor: drop legacy users.organization_id, make membership the
source of truth`).

**Open question**: neither the build-log phase docs nor the commit history
record the specific product/business event that made multi-org membership
newly necessary at that point (e.g. a named customer needing to operate
across two organizations, or a decision to ship a superadmin console). The
*mechanism* (a many-to-many membership table) is fully documented; the
originating *business trigger* is not — this ADR does not invent one.

## Options considered

This ADR only documents the shape that shipped; the phase docs do not record
alternative shapes that were considered and rejected (unlike ADR-001/ADR-002,
which document explicit Option A/B/C tradeoffs). No "roads not taken" are
recorded for this decision — treat that as an open question rather than
assuming none were discussed.

### Option A — `user_organization_memberships` table (shipped)

Roles move off `users` onto a new `UserOrganizationMembership` row keyed on
`(user_id, organization_id)` with a `role` column. A user can hold a distinct
role in each organization they belong to. The active organization for a
request travels on an `X-Organization-Id` header rather than being implicit
on the user row.

## Decision

We ship Option A, as verified in the current codebase:

- `apps/backend/app/models/user.py` has **no** `role` or `organization_id`
  column. It exposes `memberships` (a relationship to
  `UserOrganizationMembership`) and a computed `is_superadmin` property.
- `apps/backend/app/models/user_organization_membership.py` defines
  `UserOrganizationMembership`: `user_id` FK, `organization_id` FK, `role`
  (the `UserRole` enum), unique on `(user_id, organization_id)`.
- The active organization for a request is resolved from the
  `X-Organization-Id` header by `get_active_membership` in
  `apps/backend/app/core/rbac.py` (module docstring, lines 15–19):
  - If the header is present, look up the matching membership row or 403.
  - If the header is absent, use the caller's sole membership, or 400 if they
    have zero or more than one.
- **Superadmin is config-defined, never stored.** `User.is_superadmin`
  (`apps/backend/app/models/user.py:64-69`) is a property that checks whether
  the caller's (Hanko-verified) email, lower-cased, is in
  `settings.superadmin_emails` — parsed from the comma-separated
  `SUPERADMIN_EMAIL` env var in `apps/backend/app/core/config.py:76-81`.
  There is no `is_superadmin` column and no database row that, by itself,
  grants superadmin. `require_superadmin` in `app/core/rbac.py:57-73`
  enforces this for `/superadmin/*` routes and deliberately does **not**
  depend on `get_active_membership` — the superadmin surface acts across all
  organizations, not through any one membership.
  - Note: `UserRole` (`apps/backend/app/models/enums.py`) still carries a
    `superadmin` enum value, used to reject `superadmin` as an invitation
    role (`apps/backend/app/schemas/organization_invitation.py:10`) and to
    label it in notification copy (`apps/backend/app/services/notifications.py:54`).
    It is not assignable as a membership row's `role` in the normal flow —
    superadmin status never comes from a `UserOrganizationMembership` row.
- ADR-001's old single-role, per-route gate factory (`app/core/rbac.py`, not
  named here since it is obsolete — see ADR-001 for the original name) no
  longer exists anywhere in `apps/backend/app`. Its replacements are:
  - `require_membership_roles(*allowed)` (`app/core/rbac.py:136-155`) — 403s
    when the *active membership's* role is not in the allow-list. A user who
    is `lp` in Org A and `admin` in Org B is treated as `admin` when acting
    through the Org B membership.
  - `require_tenant_user` (`app/core/rbac.py:76-85`) — rejects superadmins
    from tenant-only, non-membership flows.
  - `require_superadmin` (`app/core/rbac.py:57-73`) — see above.
- LP (investor) visibility does not go through `get_active_membership` at
  all for the investor-portal routes (see the rbac.py module docstring,
  line 18-19); those resolve access via `app.core.investor_access`. Where LP
  scoping is expressed as a query fragment, it lives in
  `apps/backend/app/repositories/lp_scope.py`, which further restricts
  `InvestorContact` linkage to the active membership's `organization_id` so a
  contact binding in one org can't be exercised through a membership in
  another.

## Consequences

### What we get

- **True multi-org membership.** A single `User` row can hold independent
  roles in as many organizations as it has membership rows for, satisfying
  exactly the gap ADR-001 predicted.
- **Superadmin cannot be escalated via a database write.** Because
  `is_superadmin` is computed from `SUPERADMIN_EMAIL` (an environment/config
  value) rather than read from a database column, a compromised database
  write path (e.g. an admin-level SQL injection, a bug in an admin-facing
  update endpoint, or a malicious membership row) cannot by itself grant
  superadmin. An attacker would need to control the deployment's
  configuration, not just a database row, to mint a superadmin. This is a
  real security property worth preserving: do not reintroduce a stored
  "is_superadmin" or "role=superadmin" column without re-deciding this
  tradeoff explicitly.
- **Scoping is explicit per-request, not implicit on the session.** Every
  org-scoped request states which organization it's acting on via
  `X-Organization-Id`, rather than relying on a value cached on the user row
  at login time. This also means a stale cached "current org" can't leak
  across a user's memberships.

### What we accept

- **An extra header dependency.** Every org-scoped route now requires the
  frontend to send `X-Organization-Id` and to resolve which org is "active."
  Frontend implementation for this (active-org context/selection) lives in
  the `@edenscale/shared` package per `CLAUDE.md`; this ADR does not audit
  that code.
- **A 400 for ambiguous callers.** A user with zero or multiple memberships
  and no `X-Organization-Id` header gets a 400, not a default org. This is
  intentional (no silent "pick one for me" behavior) but is a real UX
  surface the frontend must handle.
- **A vestigial `UserRole.superadmin` enum member.** It is not used as a
  membership role but is still referenced in invitation validation and
  notification labeling (see above). This is a minor internal-consistency
  wart, not a security gap — verified no code path assigns it to a
  `UserOrganizationMembership.role`.

## Implementation pointers

- `apps/backend/app/core/rbac.py` — `get_active_membership`,
  `require_membership_roles`, `require_tenant_user`, `require_superadmin`,
  and `get_current_user_record`.
- `apps/backend/app/models/user_organization_membership.py` — the
  `UserOrganizationMembership` model.
- `apps/backend/app/models/user.py` — `User.memberships` relationship and
  `User.is_superadmin` property.
- `apps/backend/app/repositories/lp_scope.py` — LP-visibility query
  fragments scoped to the active membership's organization.
- `apps/backend/app/repositories/user_organization_membership_repository.py`
  — CRUD for membership rows.
- `apps/backend/app/core/config.py` — `SUPERADMIN_EMAIL` /
  `superadmin_emails`.
- Build log: `docs/Auto Run Docs/2026-04-30-Edenscale-2/Phase-01-*` through
  `Phase-08-*` — historical record of the migration, including the alembic
  migration that backfilled `user_organization_memberships` from the legacy
  `users.organization_id` column and the later commit that dropped it
  (`995610d4`).

## Revisit when

- SCIM / SSO provisioning is adopted and role/org assignment needs to be
  driven by an external directory instead of admin-issued membership rows.
- The vestigial `UserRole.superadmin` enum value causes real confusion (e.g.
  a new contributor tries to grant superadmin via a membership role) — at
  that point, consider a dedicated invitation-role enum that excludes it
  entirely rather than rejecting it ad hoc in `organization_invitation.py`.
- `docs/architecture/rbac-model.md`, `api-layering.md`, `system-overview.md`,
  and `database-schema.md` are updated to match this model — as of this
  writing they still describe the ADR-001 shape (`users.role`,
  `users.organization_id`, and the obsolete per-route role gate) and were
  flagged as out-of-scope drift by the plan that produced this ADR
  (plan 010). Someone should reconcile them; see plan 010's report for the
  specific stale lines.
