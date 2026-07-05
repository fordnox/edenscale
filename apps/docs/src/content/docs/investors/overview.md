---
title: Investor (LP) overview
description: What the investor role is, how LP access is granted and scoped, and what investors can see and do on the platform.
---

Investors — Limited Partners, or **LPs** — use the investor portal (served under `/investor`) to follow their commitments: fund performance, capital calls, distributions, documents, and letters from the fund manager. This section documents exactly what the platform exposes to the investor role and how that access is enforced by the backend.

## The `lp` role

There is no global "investor" account type. A user's role lives on their **organization membership** (`UserRole` enum: `superadmin`, `admin`, `fund_manager`, `lp` — see `apps/backend/app/models/enums.py`). The same login can be an `lp` in one organization and an `admin` in another; the investor portal only surfaces the LP memberships, while manager memberships live in the separate manager app.

Every org-scoped API call resolves the acting membership from the **`X-Organization-Id` header** (`get_active_membership` in `apps/backend/app/core/rbac.py`):

- Header present → the matching membership row is used (403 if the user is not a member).
- Header absent → works only when the user has exactly one membership; otherwise the API responds `400 X-Organization-Id required`.

Write and admin endpoints are wrapped in `require_membership_roles(admin, fund_manager, superadmin)`. The `lp` role is never in that allow-list, so all management endpoints return `403 Insufficient role` for investors.

## How an investor gets access

Access flows from an email invitation, not from self-registration:

1. A fund manager creates an **investor entity** (the legal LP — a fund of funds, family office, individual…) and adds **contacts** to it by email.
2. The manager sends an **invitation** for the `lp` role to that email.
3. The invitee signs in and calls `POST /invitations/accept`. This validates the invitation against the caller's email, creates the `lp` membership, and — crucially — **links any unclaimed `InvestorContact` rows with that email to the user**.

That `InvestorContact.user_id` linkage is the root of everything an LP can see.

## The visibility chain

LP reads are scoped by the helpers in `apps/backend/app/repositories/lp_scope.py`, always restricted to the active membership's organization (a contact binding in one org can never be exercised through a membership in another):

```
User ── InvestorContact.user_id ──▶ Investor(s) ──▶ Commitment(s) ──▶ Fund(s)
```

- **Investors**: the investor entities the user is a linked contact for.
- **Commitments**: commitments belonging to those investors.
- **Funds**: funds where one of those commitments exists. Fund visibility drives everything downstream — valuations, team roster, non-confidential fund documents, fund-scoped communications.
- **Capital call / distribution items**: only the items attached to the LP's own commitments; other investors' allocation lines are stripped from responses.

Every repository enforces this with the same pattern: roles in `_ORG_VISIBLE_ROLES` (`admin`, `fund_manager`, `superadmin`) see the whole organization, anyone else is narrowed to their LP linkage.

## What an investor can and cannot do

**Read** (always scoped to their linkage): dashboard metrics, funds and fund groups, their investor entities and own contact rows, their commitments, capital calls and distributions (own items only), fund valuations (NAV), fund team roster, documents, communications addressed to them, tasks assigned to them, their own notifications, and their own audit-log entries.

**Write** — the full LP write surface is intentionally small:

| Action | Endpoint |
| --- | --- |
| Update own profile | `PATCH /users/me` |
| Manage own notifications | `POST /notifications/read-all`, `/notifications/{id}/read`, `/notifications/{id}/archive` |
| Acknowledge a communication | `POST /communications/{id}/recipients/{recipient_id}/read` (own recipient row only) |
| Complete an assigned task | `POST /tasks/{id}/complete` |
| Accept an invitation | `POST /invitations/accept` |

Everything financial or administrative — creating or editing funds, commitments, capital calls, distributions, valuations, investors, contacts, documents, communications, tasks, invitations, roles — is manager-only.

## Investor portal pages

The `/investor` SPA (`apps/investor`) maps onto this surface: a cross-organization portfolio home, then per-organization workspaces with Dashboard, Funds, Capital Calls, Distributions, Documents, Reports, Archive, Letters, Notifications, and Profile pages.

Continue with:

- [Portfolio and funds](/docs/investors/portfolio/)
- [Capital calls and distributions](/docs/investors/capital-calls-and-distributions/)
- [Documents and communications](/docs/investors/documents-and-communications/)
- [Account, tasks and notifications](/docs/investors/account/)
- [API reference for the investor role](/docs/investors/api-reference/)
