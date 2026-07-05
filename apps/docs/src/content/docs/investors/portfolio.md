---
title: Portfolio and funds
description: What an investor sees on the dashboard and across funds, fund groups, commitments, valuations, and the fund team.
---

Everything on this page is read-only for investors and scoped to their [visibility chain](/docs/investors/overview/#the-visibility-chain): linked investor entities → commitments → funds.

## Dashboard

`GET /dashboard/overview` returns a personalized snapshot. For an LP every figure is computed from **their own** linkage, not the organization's totals:

| Metric | LP meaning |
| --- | --- |
| `funds_active` | Active funds where they hold a commitment |
| `investors_total` | Investor entities they are a linked contact for |
| `commitments_total_amount` | Sum of their own commitments |
| `capital_calls_outstanding` | Outstanding calls containing one of their allocation items |
| `distributions_ytd_amount` | Year-to-date distribution items on their commitments |
| `unread_notifications_count` / `open_tasks_count` | Their own notifications and assigned tasks |

The payload also includes `recent_funds` (up to five, with IRR/DPI), `upcoming_capital_calls` (only calls that contain their items), and `recent_communications` they are a recipient of. A user with no membership at all gets an all-zeros response rather than an error.

## Funds

- `GET /funds` lists only the funds in the active organization where the LP holds a commitment.
- `GET /funds/{fund_id}` and `GET /funds/by-slug/{slug}` apply the same gate (`membership_can_view`): no commitment in the fund → `403`.
- `GET /funds/{fund_id}/overview` returns fund metrics — committed, called, distributed, NAV, IRR, DPI, TVPI, RVPI, called percentage.

Note that the fund overview reports **fund-wide** aggregates, not the LP's slice. The investor's own position comes from their commitments and their capital-call/distribution items.

## Fund groups

`GET /fund-groups` and `GET /fund-groups/{id}` show only groups that contain at least one fund the LP is committed to.

## Investor entities and contacts

- `GET /investors` lists the investor entities the LP is a linked contact for; `GET /investors/{id}` returns one of them (with total committed and fund count) or `403`.
- `GET /investors/{investor_id}/contacts` returns **only the LP's own contact rows** for that investor. Managing contacts (add / edit / remove) is manager-only.

## Commitments

- `GET /commitments` (with optional `fund_id` / `investor_id` filters), `GET /funds/{fund_id}/commitments`, and `GET /investors/{investor_id}/commitments` all narrow to commitments belonging to the LP's investors — passing another investor's id still yields only the caller's own rows.
- `GET /commitments/{id}` returns `403` unless the commitment's investor is LP-linked.

Investors cannot create commitments or change commitment status; that workflow (`pending` → `approved` / `declined` / `cancelled`) belongs to the fund manager.

## Valuations and team

For any fund the LP can view:

- `GET /funds/{fund_id}/valuations` — NAV marks, newest first. These drive the fair-value figures shown in the portal.
- `GET /funds/{fund_id}/team` — the fund's team roster (informational; management of the roster is manager-only).
