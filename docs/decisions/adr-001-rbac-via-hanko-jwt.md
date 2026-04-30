---
type: analysis
title: 'ADR-001: RBAC via local User row keyed on Hanko subject ID'
created: 2026-04-29
tags:
  - auth
  - decision
  - rbac
related:
  - '[[System-Overview]]'
  - '[[RBAC-Model]]'
  - '[[ADR-002-Storage-Port-Pattern]]'
---

# ADR-001: RBAC via local User row keyed on Hanko subject ID

**Status:** Accepted (2026-02 / locked in during Phase 02 of the build)
**Deciders:** Backend team
**Supersedes:** none

## Context

EdenScale outsources authentication to Hanko (passkey + email magic link). Hanko issues an RS256 JWT with a stable subject claim per user. The platform still needs:

- **Authorisation** — three roles (`admin`, `fund_manager`, `lp`) with different visibility rules. See [[RBAC-Model]].
- **Tenancy** — every fund_manager belongs to a `fund_manager_firm` organization; LPs belong to an `investor_firm`.
- **Profile data** — first/last name, phone, title that admins / fund_managers can see and edit. Some of these fields the IdP does not collect.
- **Audit trail** — every mutation needs an actor user_id stable across deploys.
- **Foreign keys** — `funds.created_by_user_id`, `tasks.assigned_to_user_id`, `documents.uploaded_by_user_id`, `commitments` linked to investors via `investor_contacts.user_id`, etc. We need an integer PK to point at.

There were two reasonable shapes for this.

## Options considered

### Option A — local `users` row keyed on `hanko_subject_id` (chosen)

Mint a row in `users` on first JWT sight; key it on `hanko_subject_id`. Store `role`, `organization_id`, profile fields, and `last_login_at` locally. The Hanko JWT carries only identity; everything else lives in our DB.

```
JWT.sub  ──▶  users.hanko_subject_id  ──▶  users.id (PK)
                                              │
                                              ▼ FK target
                                  funds.created_by_user_id, etc.
```

Implementation: `app/core/rbac.py::get_current_user_record` — find-or-create on first sight, default `role = lp`, copy any name/email claims the IdP supplied.

### Option B — role + org as Hanko custom claims

Hanko supports custom JWT claims. We could set `role` and `organization_id` on the IdP user object and read them straight off the decoded JWT, with no local `users` table.

## Decision

We picked **Option A**.

## Consequences

### What we get

- **Foreign keys work.** `funds.created_by_user_id` points at an integer PK that's stable across logins. With Option B we'd either denormalise the Hanko subject string into every FK column, or add a separate `users` mapping table anyway — at which point Option A and Option B converge.
- **Role changes are immediate.** An admin can flip a user from `lp` to `fund_manager` via `PATCH /users/{id}/role` and it takes effect on the user's very next request. With custom claims we'd need to invalidate the active JWT (Hanko caches them for the session lifetime) or wait for the next refresh.
- **Audit and history work.** `audit_logs.user_id`, `last_login_at`, `created_at` all hang naturally off the local row. Option B would need either a shadow `users` table for these fields (defeating the point) or storing them on the IdP, where we have less control.
- **Profile editing is local.** `PATCH /users/me` updates first_name / last_name / phone / title in our DB without round-tripping the IdP. The `email` field is read-only in our UI because Hanko owns the sign-in identity (see `ProfilePage.tsx`).
- **Tenant scoping is one JOIN.** Repository scopes filter `WHERE organization_id = :user.organization_id`. With custom claims they'd read from the JWT, which works but couples the visibility query to the auth layer.

### What we accept

- **A "phantom" row exists for any authenticated user.** First-login auto-provisioning means we get rows for users who sign in once and never come back. We accept that — `is_active` lets us soft-disable, and the row is cheap.
- **Hanko outage = no logins, but live sessions still work.** Once a JWT is issued and we've cached the JWKS, validation is offline. Option B has the same trade-off, and Hanko's JWKS is cached for an hour anyway.
- **Two writes on first login.** First-sight provisioning does an `INSERT` inside `get_current_user_record`. We accept the extra write because it only happens once per user.
- **`hanko_subject_id` must never collide.** Our `User.hanko_subject_id` is `UNIQUE NOT NULL`. If we ever migrate to a different IdP, that column will need to be re-keyed (one-shot migration script).
- **Name/email claims may be empty.** The IdP doesn't always supply them; we default to empty strings (NOT NULL columns) and let the user fill in `PATCH /users/me`.

### Why we did not pick Option B

Custom claims would have removed the `users` table only at the cost of:

1. Putting application data (role, organization_id) in the IdP, requiring an admin write to Hanko whenever a role changes.
2. Either making FKs point at a string subject ID (ugly, no `ON DELETE`), or maintaining a mapping table — at which point we have a `users` table by another name.
3. Coupling our authorisation model to Hanko's claim plumbing. If we ever swap IdPs, we'd have to re-engineer the auth layer instead of just remapping `hanko_subject_id`.

## Implementation pointers

- Provisioning: `backend/app/core/rbac.py::get_current_user_record`.
- Role gate: `require_roles(*allowed)` in the same module.
- FK shape: see [[Database-Schema]] for every place `users.id` appears.
- Audit context: `app/middleware/audit_context.py` stashes the resolved `user.id` into a `ContextVar` so SQLAlchemy listeners record `audit_logs.user_id` for every write.

## Revisit when

- We adopt SCIM / SSO provisioning. The find-or-create-on-first-sight pattern would need to grow into an upsert keyed on email or external ID, with role pre-populated by the directory.
- We need to support a user belonging to multiple organizations. Today `users.organization_id` is a single nullable FK. A many-to-many would require a `user_organizations` table and reworking every repository scope.
