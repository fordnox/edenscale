---
type: analysis
title: Active-Org Migration Audit (Phase 02)
created: 2026-04-30
tags:
  - phase-02
  - active-membership
  - audit
related:
  - '[[Phase-02-Active-Org-Context]]'
  - '[[Phase-01-Membership-Data-Model]]'
---

# Active-Org Migration Audit

Inventory of every call site under `backend/app/routers/` and `backend/app/repositories/` that reads `current_user.organization_id` / `user.organization_id` / `users.organization_id`. These are the lines Phase 02 must replace with the new `active_membership.organization_id` / `active_membership.role` flow.

Numbers are file:line as of branch `main` at the start of Phase 02.

## Routers (`backend/app/routers/`)

- `routers/funds.py:130` — `if current_user.organization_id is None:` (create-fund guard)
- `routers/funds.py:135` — `payload["organization_id"] = current_user.organization_id`
- `routers/funds.py:162` — `fund.organization_id != current_user.organization_id` (cross-org guard, update)
- `routers/funds.py:192` — `fund.organization_id != current_user.organization_id` (cross-org guard, delete)
- `routers/fund_groups.py:27` — `if current_user.organization_id is None:` (list guard)
- `routers/fund_groups.py:30` — `organization_id=current_user.organization_id` (list scope)
- `routers/fund_groups.py:50` — `fund_group.organization_id != current_user.organization_id` (read guard)
- `routers/fund_groups.py:67` — `if current_user.organization_id is None:` (create guard)
- `routers/fund_groups.py:72` — `payload["organization_id"] = current_user.organization_id` (create scope)
- `routers/fund_groups.py:100` — `fund_group.organization_id != current_user.organization_id` (update guard)
- `routers/fund_groups.py:123` — `fund_group.organization_id != current_user.organization_id` (delete guard)
- `routers/fund_team_members.py:34` — `fund.organization_id != current_user.organization_id`
- `routers/investors.py:99` — `if current_user.organization_id is None:` (create guard)
- `routers/investors.py:104` — `payload["organization_id"] = current_user.organization_id` (create scope)
- `routers/investors.py:131` — `investor.organization_id != current_user.organization_id` (update guard)
- `routers/investors.py:161` — `investor.organization_id != current_user.organization_id` (delete guard)
- `routers/investor_contacts.py:33` — `investor.organization_id != current_user.organization_id` (read guard)
- `routers/investor_contacts.py:54` — `investor.organization_id != current_user.organization_id` (create guard)
- `routers/commitments.py:36` — `fund.organization_id != current_user.organization_id`
- `routers/capital_calls.py:38` — `fund.organization_id != current_user.organization_id`
- `routers/distributions.py:38` — `fund.organization_id != current_user.organization_id`
- `routers/documents.py:48` — `org_id = current_user.organization_id` (upload-route scope)
- `routers/communications.py:32` — `fund.organization_id != current_user.organization_id`
- `routers/tasks.py:28` — `fund.organization_id != current_user.organization_id`
- `routers/dashboard.py:64` — `Fund.organization_id == user.organization_id` (subquery scope)
- `routers/dashboard.py:78` — `Investor.organization_id == user.organization_id` (subquery scope)
- `routers/dashboard.py:104` — `current_user.organization_id is None` (top-level guard)
- `routers/users.py:53` — `if current_user.organization_id is None:` (invite-list guard)
- `routers/users.py:57` — `organization_id=current_user.organization_id` (invite-list scope)
- `routers/users.py:72` — `if current_user.organization_id is None:` (invite-create guard)
- `routers/users.py:77` — `payload["organization_id"] = current_user.organization_id` (invite-create scope)
- `routers/users.py:102` — `target.organization_id != current_user.organization_id` (role-update cross-org guard)

`routers/notifications.py` and `routers/audit_logs.py` did not turn up direct hits on these patterns; both will still need a Phase 02 review (they accept a `current_user` dep and likely scope queries downstream — confirm during the migration pass).

## Repositories (`backend/app/repositories/`)

- `repositories/fund_repository.py:43` — `if user.organization_id is None:`
- `repositories/fund_repository.py:45` — `Fund.organization_id == user.organization_id` (list scope)
- `repositories/fund_repository.py:65` — `fund.organization_id == user.organization_id` (visibility check)
- `repositories/capital_call_repository.py:74` — `if user.organization_id is None:`
- `repositories/capital_call_repository.py:77` — `Fund.organization_id == user.organization_id`
- `repositories/capital_call_repository.py:108` — `fund.organization_id == user.organization_id`
- `repositories/investor_repository.py:46` — `if user.organization_id is None:`
- `repositories/investor_repository.py:48` — `Investor.organization_id == user.organization_id`
- `repositories/investor_repository.py:63` — `investor.organization_id == user.organization_id`
- `repositories/commitment_repository.py:36` — `if user.organization_id is None:`
- `repositories/commitment_repository.py:39` — `Fund.organization_id == user.organization_id`
- `repositories/commitment_repository.py:74` — `fund.organization_id == user.organization_id`
- `repositories/distribution_repository.py:67` — `if user.organization_id is None:`
- `repositories/distribution_repository.py:70` — `Fund.organization_id == user.organization_id`
- `repositories/distribution_repository.py:101` — `fund.organization_id == user.organization_id`
- `repositories/document_repository.py:24` — `org_id = user.organization_id`
- `repositories/document_repository.py:89` — `document.organization_id == user.organization_id`
- `repositories/document_repository.py:95` — `fund.organization_id == user.organization_id`
- `repositories/document_repository.py:135` — `document.organization_id == user.organization_id`
- `repositories/document_repository.py:141` — `fund.organization_id == user.organization_id`
- `repositories/communication_repository.py:42` — `if user.organization_id is None:`
- `repositories/communication_repository.py:45` — `Fund.organization_id == user.organization_id`
- `repositories/communication_repository.py:91` — `if user.organization_id is None:`
- `repositories/communication_repository.py:94` — `Fund.organization_id == user.organization_id`
- `repositories/communication_repository.py:141` — `fund.organization_id == user.organization_id`
- `repositories/communication_repository.py:170` — `fund.organization_id == user.organization_id`
- `repositories/task_repository.py:35` — `org_id = user.organization_id`
- `repositories/task_repository.py:77` — `fund.organization_id == user.organization_id`
- `repositories/task_repository.py:92` — `fund.organization_id == user.organization_id`

These repository methods accept a `user` argument and derive scope from it. The cleanest Phase 02 plan is to change those signatures to accept `organization_id` (or the active membership) directly, so the routers keep "what org am I acting in" logic out of the data layer. Each callsite in the routers will need to pass `active_membership.organization_id` instead of the whole `User`.

## Out-of-scope hits (intentional, do NOT migrate in Phase 02)

- `repositories/user_organization_membership_repository.py:84` — docstring reference to `users.organization_id` describing what the bulk-seed reads. Legacy by design.
- `repositories/user_organization_membership_repository.py:96` — `self.get(user.id, user.organization_id)` inside the bulk seeder; the seeder's whole purpose is to read the legacy column.
- `repositories/user_organization_membership_repository.py:102` — same, seeder writes from legacy column.
- `repositories/user_repository.py` — none today (was checked, no hits).
- `core/audit.py:147` — `organization_id = user.organization_id if user is not None else None`. Audit-log writer derives the org from the user. This is a separate, deliberate question (audit logs may want the *active* org, not the legacy column) — flag for Phase 02 but the task list does not explicitly include it. Recommend: switch to `active_membership.organization_id` once `get_active_membership` exists; until then, leave it on the legacy column to avoid breaking pre-multi-org audit rows.
- `core/rbac.py` — no current `organization_id` reads; `get_current_user_record` returns the raw `User`. Phase 02 will add `get_active_membership` here as a sibling dep.

## Routers verified clean of legacy column reads

- `routers/organizations.py` — superadmin/global org management; should stay on `require_roles(superadmin)` per Phase 02 guidance.
- `routers/notifications.py` — no `current_user.organization_id` hits in grep; still needs a manual scope review during migration (per-user notifications may already be user-scoped, not org-scoped).
- `routers/audit_logs.py` — no `current_user.organization_id` hits in grep; same caveat as notifications.

## Migration headcount

- 32 hits in routers across 14 files
- 29 hits in repositories across 9 files
- Plus one out-of-scope reference in `core/audit.py:147` to track separately
