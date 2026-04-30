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
---

# Database Schema

The schema is described authoritatively in [`db.dbml`](../../db.dbml) and materialised by Alembic in `backend/app/alembic/versions/`. Postgres is used in production; SQLite is used for local dev and the test suite. There are **18 tables** and **10 enums**, organised into four functional groups.

## Entity groups

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Identity & Tenancy                                                   │
│                                                                         │
│   organizations ──┬──< users                                            │
│                   ├──< fund_groups                                      │
│                   ├──< funds                                            │
│                   ├──< investors                                        │
│                   └──< documents (optional)                             │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Funds & Commitments                                                  │
│                                                                         │
│   fund_groups ──< funds ──┬──< fund_team_members >── users              │
│                           ├──< commitments >── investors                │
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
| `users`         | Local user row keyed on `hanko_subject_id`. Holds `role` (`admin`/`fund_manager`/`lp`), `organization_id`, profile fields. See [[ADR-001-RBAC-Via-Hanko-JWT]]. |

## 2. Funds & Commitments

| Table                | Purpose                                                                     |
| -------------------- | --------------------------------------------------------------------------- |
| `fund_groups`        | Optional grouping ("Growth Series", "Venture Series") under an organization.|
| `funds`              | A vintage. Status: `draft → active → closed → liquidating → archived`.      |
| `fund_team_members`  | Many-to-many users ↔ funds with a per-fund title. Unique on `(fund_id, user_id)`. |
| `investors`          | An LP entity. Distinct from the `users` who represent it.                   |
| `investor_contacts`  | Bridge from `investors` to `users` (the human representatives). One can be `is_primary=true`. |
| `commitments`        | Investor commits a `committed_amount` to a `fund`. Unique on `(fund_id, investor_id)`. Tracks running `called_amount` and `distributed_amount`. |

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

## Enums (10)

`user_role`, `organization_type`, `fund_status`, `commitment_status`, `capital_call_status`, `distribution_status`, `document_type`, `communication_type`, `notification_status`, `task_status`. Definitions live in [`backend/app/models/enums.py`](../../backend/app/models/enums.py); literal values match the dbml exactly.

## Migrations

- `make migration` prompts for a name and runs `alembic revision --autogenerate`.
- `make upgrade` / `make downgrade` step one revision.
- The initial cut of every table lives in `app/alembic/versions/d496f70bae71_initial_schema_from_dbml.py`.
- The Alembic folder is excluded from all linters in `make lint`.

## Audit fan-out

`app/core/audit.py` registers `after_insert` / `after_update` / `after_delete` listeners on `Organization`, `User`, `Fund`, `Commitment`, `CapitalCall`, `Distribution`, `Document`, `Communication`, and `Task`. Each write produces one `audit_logs` row with `entity_type`, `entity_id`, `action`, a JSON `metadata` diff, and the actor + IP captured by `AuditContextMiddleware`. Listeners run inside the originating transaction so a rollback discards both the business write and its audit trail.

## Visibility and scoping

Most tables carry `organization_id` directly or transitively. The repository layer (see [[API-Layering]]) implements three role-aware scopes:

- **admin** — global.
- **fund_manager** — `WHERE organization_id = :user.organization_id`.
- **lp** — joins through `investor_contacts → investors → commitments` to reach the funds and per-fund records they have a stake in.

For the per-entity rules see [[RBAC-Model]].
