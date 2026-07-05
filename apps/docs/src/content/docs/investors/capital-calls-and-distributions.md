---
title: Capital calls and distributions
description: How investors see capital calls and distributions, and why they only ever see their own allocation items.
---

Capital calls and distributions are created, allocated, sent, and settled by the fund manager. Investors have a read-only view — and a deliberately narrowed one.

## What an investor sees

- `GET /capital-calls` and `GET /distributions` (both filterable by `fund_id` and `status_filter`), plus the per-fund variants `GET /funds/{fund_id}/capital-calls` and `GET /funds/{fund_id}/distributions`, list only calls/distributions that include **at least one item on the LP's own commitments**.
- `GET /capital-calls/{id}` and `GET /distributions/{id}` require the same — owning an item — otherwise `403`.

### Item stripping

A capital call or distribution row carries every investor's allocation items, but the API filters the serialized response before it leaves the backend (`_scope_items_for_membership` in `apps/backend/app/routers/capital_calls.py` and `distributions.py`): an LP receives **only their own allocation line(s)**. The call's headline `amount` is the full call amount, but the `items` array never exposes other investors' allocations, amounts paid, or notes.

## Status lifecycle

Both objects move through manager-driven states (`CapitalCallStatus` / `DistributionStatus`):

```
draft → scheduled → sent → partially_paid → paid
                      └──────────▶ cancelled        (calls can also become overdue)
```

Investors only ever see calls/distributions once they contain an item for them; in practice the portal surfaces them from `sent` onward, and the **Sent** transition is what triggers the investor's email/in-app notification (`customer.capital_call` / `customer.distribution`).

## What an investor cannot do

All mutations are manager-only and return `403 Insufficient role` for LPs:

- create or edit a call/distribution (`POST`, `PATCH /{id}`)
- add or edit allocation items (`POST /{id}/items`, `PATCH /{id}/items/{item_id}`) — including recording payments: an LP **cannot mark their own item paid**; the manager records `amount_paid` / `paid_at`
- send or cancel (`POST /{id}/send`, `POST /{id}/cancel`)
