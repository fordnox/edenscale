---
type: reference
title: Database Schema
created: 2026-04-29
tags:
  - architecture
  - database
  - postgres
related:
  - '[[System-Overview]]'
  - '[[API-Layering]]'
  - '[[RBAC-Model]]'
  - '[[ADR-003-Per-Org-Membership-Roles]]'
---

# Database Schema

> **2026-07-22 correction:** `db.dbml` **no longer exists** — it was deleted
> in commit `883ddeef` ("move files") and never replaced. There is no single
> authoritative schema-description file; `apps/backend/app/models/*.py` plus
> the Alembic migration history are what's actually authoritative now. This
> pass also corrects the `users` row and the RBAC-adjacent "Visibility and
> scoping" section below (the reason this file was touched) and removes
> `fund_team_members`, which was dropped. It does **not** attempt a full
> re-audit of every table/enum count or the newer tables (`bank_statement_imports`,
> `bank_payment_transactions`, `fund_valuations`, `organization_invitations`,
> `notification_logs`, `user_organization_memberships`) against this doc's
> entity-group diagrams — that inventory has likely drifted too (the
> "18 tables and 10 enums" figure below is **unverified** and should not be
> trusted) but is a separate cleanup from the RBAC drift this pass targets.

The schema is materialised by Alembic in `backend/app/alembic/versions/`; the initial cut (from the deleted dbml) lives in `d496f70bae71_initial_schema_from_dbml.py`. Postgres is required in every environment, local dev included — see [[System-Overview]]'s corrected topology note. There are **18 tables** and **10 enums** *(unverified count, carried over — see correction note above)*, organised into four functional groups.

## Entity groups

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Identity & Tenancy                                                   │
│                                                                         │
│   organizations ──┬──< user_organization_memberships >── users          │
│                   ├──< fund_groups                                      │
│                   ├──< funds                                            │
│                   ├──< investors                                        │
│                   └──< documents (optional)                             │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Funds & Commitments                                                  │
│                                                                         │
│   fund_groups ──< funds ──┬──< commitments >── investors                │
│                           ├──< capital_calls                            │
│                           ├──< distributions                            │
│                           └──< communications                           │
│                                                                         │
│   investors ──< investor_contacts >── users (optional)                  │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Capital Flows                                                        │
│                                                                         │
│   capital_calls ──< capital_call_items >── commitments                  │
│   distributions ──< distribution_items >── commitments                  │
│                                                                         │
│   commitments running totals: called_amount, distributed_amount         │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Supporting                                                           │
│                                                                         │
│   documents (org | fund | investor scoped, file_url via StoragePort)    │
│   communications ──< communication_recipients >── users                 │
│   notifications  (per-user fan-out, status: unread/read/archived)       │
│   tasks          (assigned_to_user_id, fund_id optional)                │
│   audit_logs     (every mutation on the registered models)              │
└─────────────────────────────────────────────────────────────────────────┘
```

## 1. Identity & Tenancy

| Table           | Purpose                                                                            |
| --------------- | ---------------------------------------------------------------------------------- |
| `organizations` | Tenant root. Type is one of `fund_manager_firm`, `investor_firm`, `service_provider`. |
| `users`         | Local user row keyed on `hanko_subject_id`, plus profile fields. **Has no `role` and no `organization_id`** — those columns were dropped (`app/alembic/versions/..._drop_users_legacy_identity_columns.py`). See [[ADR-001-RBAC-Via-Hanko-JWT]] for why a local user row exists at all. |
| `user_organization_memberships` | Per-`(user, organization)` role row (`admin`/`fund_manager`/`lp`) — the source of truth for who belongs to which org and with what role. A user can hold a different role in each org they're a member of. Superadmin is **not** a row here — it's config-defined via `SUPERADMIN_EMAIL` and checked at the `User.is_superadmin` property. See [[ADR-003-Per-Org-Membership-Roles]] and [[RBAC-Model]]. |

## 2. Funds & Commitments

| Table                | Purpose                                                                     |
| -------------------- | --------------------------------------------------------------------------- |
| `fund_groups`        | Optional grouping ("Growth Series", "Venture Series") under an organization.|
| `funds`              | A vintage. Status: `draft → active → closed → liquidating → archived`.      |
| `investors`          | An LP entity. Distinct from the `users` who represent it.                   |
| `investor_contacts`  | Bridge from `investors` to `users` (the human representatives). One can be `is_primary=true`. |
| `commitments`        | Investor commits a `committed_amount` to a `fund`. Unique on `(fund_id, investor_id)`. Tracks running `called_amount` and `distributed_amount`. |

> `fund_team_members` (many-to-many `users` ↔ `funds` with a per-fund title)
> was in an earlier version of this table; the table itself was dropped
> (`app/alembic/versions/..._drop_fund_team_members.py`) and has no
> corresponding model — removed here rather than left stale.

## 3. Capital Flows

| Table                | Purpose                                                                     |
| -------------------- | --------------------------------------------------------------------------- |
| `capital_calls`      | Header for a call against a fund. Status: `draft → scheduled → sent → partially_paid → paid` (plus `overdue` / `cancelled`). |
| `capital_call_items` | Per-commitment allocation. `amount_due` is computed pro-rata on send, `amount_paid` is posted as wires arrive. Unique on `(capital_call_id, commitment_id)`. |
| `distributions`      | Header for a distribution. Same status machine minus `overdue`.             |
| `distribution_items` | Per-commitment allocation, mirror shape of `capital_call_items`.            |

The repository layer keeps `commitments.called_amount` and `commitments.distributed_amount` in sync as items are paid — see `app/services/allocation.py` and `app/repositories/capital_call_repository.py`.

## 4. Supporting

| Table                      | Purpose                                                                |
| -------------------------- | ---------------------------------------------------------------------- |
| `documents`                | Scoped to org / fund / investor (any combination nullable). `file_url` is canonical; bytes live behind `StoragePort`. See [[ADR-002-Storage-Port-Pattern]]. |
| `communications`           | Letter / announcement / message header.                                |
| `communication_recipients` | Per-recipient delivery row, with `delivered_at` / `read_at`. **Unique on `(communication_id, user_id)`** — a user that's primary on two investors holding commitments in the **same** fund will collide on a fund-wide send. |
| `notifications`            | Per-user fan-out for in-app bell. Status: `unread / read / archived`.  |
| `tasks`                    | Assignable work items, optional `fund_id` scope.                       |
| `audit_logs`               | Append-only trail. Written by SQLAlchemy ORM listeners in `app/core/audit.py` for every mutation on the registered entities, plus manual `record_audit` calls (e.g. login). |

## Enums (unverified count — see correction note at top of file)

Includes `membership_role` (**not** `user_role`; the old `user_role` Postgres enum type was dropped along with `users.role` — see `app/alembic/versions/..._drop_users_legacy_identity_columns.py`, which explicitly drops the `user_role` type once no column references it), `organization_type`, `fund_status`, `commitment_status`, `capital_call_status`, `distribution_status`, `document_type`, `communication_type`, `notification_status`, `task_status`. Definitions live in [`backend/app/models/enums.py`](../../backend/app/models/enums.py) — the dbml they used to mirror no longer exists (see top of file), so `enums.py` is now the source of truth, not a mirror.

## Migrations

- `make migration` prompts for a name and runs `alembic revision --autogenerate`.
- `make upgrade` / `make downgrade` step one revision.
- The initial cut of every table lives in `app/alembic/versions/d496f70bae71_initial_schema_from_dbml.py`.
- The Alembic folder is excluded from all linters in `make lint`.

## Audit fan-out

**2026-07-22 correction:** this section previously listed nine specific
audited models as if `app/core/audit.py` used an allowlist. It doesn't —
`_ENTITY_TYPES` (verified in the file) now covers essentially every mapped
model (`Organization`, `OrganizationInvitation`, `User`,
`UserOrganizationMembership`, `Fund`, `FundGroup`, `FundValuation`,
`Investor`, `InvestorContact`, `Commitment`, `CapitalCall`,
`CapitalCallItem`, `BankStatementImport`, `BankPaymentTransaction`,
`Distribution`, `DistributionItem`, `Document`, `Communication`,
`CommunicationRecipient`, `Task`, `Notification`), with only `AuditLog`
itself and `NotificationLog` deliberately excluded (`_UNAUDITED_MODELS`).
The module docstring notes a test asserts `_ENTITY_TYPES` + `_UNAUDITED_MODELS`
covers the full ORM registry, so a newly added model that's forgotten here
fails the test loudly rather than silently losing its audit trail — this
is now an opt-out list, not an opt-in one.

`app/core/audit.py` registers `after_insert` / `after_update` / `after_delete` listeners on every model above. Each write produces one `audit_logs` row with `entity_type`, `entity_id`, `action`, a JSON `metadata` diff, and the actor + IP captured by `AuditContextMiddleware`. Listeners run inside the originating transaction so a rollback discards both the business write and its audit trail.

## Visibility and scoping

**2026-07-22 rewrite** — the previous version of this section described
the pre-membership model (`WHERE organization_id = :user.organization_id`,
implying a role column directly on `users`). Verified against the current
repository layer (see [[API-Layering]] and [[RBAC-Model]] for the full
per-entity table):

Most tables carry `organization_id` directly or transitively. Every
org-scoped repository method takes a `UserOrganizationMembership` (never a
bare `User`) and scopes by **`membership.organization_id`** — the
organization resolved from the request's `X-Organization-Id` header, not a
column on `users` (there is no such column). The repository layer
implements two role-aware scopes per entity, keyed on the *active
membership's* role:

- **admin / fund_manager** — `WHERE <entity>.organization_id = :membership.organization_id`, or the same filter reached transitively through `fund_id`. Verified identical for both roles across every entity repository checked — `admin` has no broader data visibility, only extra member-management endpoints (see [[RBAC-Model]]).
- **lp** — joins through `investor_contacts → investors → commitments`, filtered by `Investor.organization_id == membership.organization_id` (`app/repositories/lp_scope.py`), to reach the funds and per-fund records they have a stake in.

Superadmin is not a third scope here at all: superadmin status is never a
membership row, and `get_active_membership` (`app/core/rbac.py`) explicitly
rejects superadmins, so none of these org-scoped queries ever run for a
superadmin caller — their entire surface is the separate `/superadmin/*`
routes (organizations, users, memberships), not these entity tables. **If
you hand-roll a query here without threading the active membership through,
you will produce an unscoped cross-tenant query** — this is the specific
mistake this correction exists to prevent.

For the per-entity rules see [[RBAC-Model]].
