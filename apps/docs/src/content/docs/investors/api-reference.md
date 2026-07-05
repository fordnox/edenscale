---
title: "Investor role: API reference"
description: Every endpoint an LP-role user can call, with the scoping rule applied to each, plus the complete LP write surface.
---

Complete inventory of the API surface reachable with an `lp` membership. Unless marked otherwise, endpoints are org-scoped and resolve the acting membership from the `X-Organization-Id` header (optional when the user belongs to exactly one organization). Everything not listed here — and every `POST`/`PATCH`/`DELETE` on the resources below except the write surface at the end — returns `403 Insufficient role` for LPs.

## Read endpoints

### Dashboard

| Endpoint | LP scoping |
| --- | --- |
| `GET /dashboard/overview` | Personalized metrics computed from the LP's own commitments, calls, distributions, notifications, and tasks. All-zeros for users with no membership. |

### Funds and fund groups

| Endpoint | LP scoping |
| --- | --- |
| `GET /funds` | Funds in the active org where the LP holds a commitment |
| `GET /funds/by-slug/{slug}` | Same commitment gate; `403` otherwise |
| `GET /funds/{fund_id}` | Same commitment gate |
| `GET /funds/{fund_id}/overview` | Fund-wide metrics (committed, called, distributed, NAV, IRR, DPI, TVPI, RVPI) — not the LP's slice |
| `GET /funds/{fund_id}/valuations` | NAV marks, newest first, for viewable funds |
| `GET /funds/{fund_id}/team` | Team roster for viewable funds |
| `GET /fund-groups` | Groups containing a fund the LP is committed to |
| `GET /fund-groups/{id}` | Same gate |

### Investors, contacts, commitments

| Endpoint | LP scoping |
| --- | --- |
| `GET /investors` | Investor entities the LP is a linked contact for |
| `GET /investors/{id}` | Same linkage gate; includes total committed and fund count |
| `GET /investors/{investor_id}/contacts` | Only the LP's **own** contact rows; `403` if none |
| `GET /commitments` | Only commitments of LP-linked investors (filters cannot widen this) |
| `GET /commitments/{id}` | `403` unless the commitment's investor is LP-linked |
| `GET /funds/{fund_id}/commitments` | Own commitments within the fund |
| `GET /investors/{investor_id}/commitments` | Own commitments for the investor |

### Capital calls and distributions

| Endpoint | LP scoping |
| --- | --- |
| `GET /capital-calls` | Only calls containing an item on the LP's commitments; other investors' items stripped from the payload |
| `GET /capital-calls/{id}` | Must own an item; response filtered to own items |
| `GET /funds/{fund_id}/capital-calls` | Same, per fund |
| `GET /distributions` | Same item-ownership scoping as capital calls |
| `GET /distributions/{id}` | Must own an item; own items only |
| `GET /funds/{fund_id}/distributions` | Same, per fund |

### Documents and communications

| Endpoint | LP scoping |
| --- | --- |
| `GET /documents` | Investor-linked documents, self-uploaded documents, and non-confidential documents on committed funds; confidential fund docs hidden |
| `GET /documents/{id}` | Same rule |
| `GET /communications` | Communications where the LP is a recipient (directly or via linked contact) or sender; unrelated drafts hidden |
| `GET /communications/{id}` | Recipient required; `403` otherwise |
| `GET /funds/{fund_id}/communications` | Same, per fund |

### Tasks, notifications, audit, account

| Endpoint | LP scoping |
| --- | --- |
| `GET /tasks` | Forced to tasks assigned to the LP (the `assignee` param is overridden) |
| `GET /tasks/{id}` | Only tasks assigned to or created by the LP |
| `GET /funds/{fund_id}/tasks` | Own assignments within the fund |
| `GET /notifications` | Own notifications only (no org header needed) |
| `GET /audit-logs` | Active org, `user_id` forced to the LP's own id |
| `GET /users/me` | Own user record (no org header needed) |
| `GET /users/me/memberships` | Own memberships across orgs |
| `GET /invitations/pending-for-me` | Pending invitations for the caller's email |

## Write endpoints available to LPs

| Endpoint | Behavior |
| --- | --- |
| `PATCH /users/me` | Update own profile (self-editable fields only) |
| `POST /notifications/read-all` | Mark all own notifications read |
| `POST /notifications/{id}/read` | Mark one read; ownership-guarded |
| `POST /notifications/{id}/archive` | Archive one; ownership-guarded |
| `POST /communications/{id}/recipients/{recipient_id}/read` | Read-receipt on the LP's own recipient row only |
| `POST /tasks/{id}/complete` | Complete a task assigned to the LP (metadata edits stay forbidden) |
| `POST /invitations/accept` | Accept an invitation addressed to the caller's email; links investor contacts |
| `POST /documents/upload-init` / `PUT /documents/upload/{key}` | Stage and push file bytes (≤ 100 MB); creating the document record remains manager-only |

## Onboarding endpoints (any authenticated user)

These are guarded only by base authentication, so an LP-role user can technically call them even though they are onboarding/utility surfaces rather than LP features:

| Endpoint | Behavior |
| --- | --- |
| `GET /organizations` / `GET /organizations/{id}` | List / fetch organizations |
| `POST /organizations/self-serve` | Create a new fund-manager org; the caller becomes its **admin** |
| `GET /organizations/demo` / `POST /organizations/demo/join` | Discover / join the seeded demo org as `fund_manager` |

## Fully forbidden areas

- `/superadmin/*` — config-defined superadmins only.
- All create/edit/send/cancel/delete operations on funds, fund groups, investors, contacts, commitments, capital calls, distributions, valuations, team members, documents (records), communications, tasks (create/metadata), invitations (issue/revoke/resend), users (roster and role changes), and organizations (create/update/delete).

Enforcement lives in `apps/backend/app/core/rbac.py` (`require_membership_roles`), `apps/backend/app/repositories/lp_scope.py` (linkage queries), and each repository's `list_for_membership` / `membership_can_view` / `membership_can_manage` methods.
