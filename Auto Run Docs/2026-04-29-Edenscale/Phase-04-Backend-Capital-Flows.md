# Phase 04: Backend — Capital Calls And Distributions

This phase builds the capital flow engine. Capital calls and distributions follow nearly identical patterns: a parent record tied to a fund, a status lifecycle (`draft → scheduled → sent → partially_paid → paid` or cancelled), and a set of line items that allocate amounts across active commitments. The crucial business rule: every time a line item changes paid amount, the parent's status and the linked commitment's running totals must be recomputed in the same transaction.

## Tasks

- [ ] Read Phase 03's commitment repository, especially `recompute_totals`, before extending it; review the `capital_call`, `capital_call_item`, `distribution`, `distribution_item` model files from Phase 01 so the foreign keys and unique constraints are correct

- [ ] Implement Capital Calls:
  - `backend/app/schemas/capital_call.py` — `CapitalCallCreate` (fund_id, title, description, due_date, call_date, amount), `CapitalCallUpdate`, `CapitalCallRead` with nested `items: list[CapitalCallItemRead]` and `fund: FundSummary`, plus `CapitalCallItemCreate`/`Update`/`Read`
  - `backend/app/repositories/capital_call_repository.py` — `list_for_user(user, fund_id=None, status=None)` (RBAC: admin all; fund_manager org-scoped; lp only via their commitments → items), `get_with_items`, `create_draft`, `update`, `add_items` (bulk-insert allocations from a list of `(commitment_id, amount_due)` tuples; rejects when commitment.fund_id != call.fund_id), `set_item_payment(item_id, amount_paid, paid_at)`, `transition_status(call_id, new_status)` enforcing the lifecycle, `recompute_status(call_id)` that derives the parent status from item totals
  - `backend/app/routers/capital_calls.py` — `GET /capital-calls`, `GET /capital-calls/{id}`, `POST /capital-calls`, `PATCH /capital-calls/{id}`, `POST /capital-calls/{id}/items`, `PATCH /capital-calls/{id}/items/{item_id}` (records a payment; updates parent + commitment totals atomically), `POST /capital-calls/{id}/send` (transitions draft/scheduled → sent and stamps `call_date`), `POST /capital-calls/{id}/cancel`
  - Add nested route `GET /funds/{fund_id}/capital-calls` on the funds router for the FundDetail page
  - Mount under `/capital-calls`

- [ ] Implement Distributions (parallel to Capital Calls):
  - Schemas, repository, router mirror the capital call pattern — `Distribution` parent + `DistributionItem` line items
  - Endpoints: `GET /distributions`, `GET /distributions/{id}`, `POST /distributions`, `PATCH /distributions/{id}`, `POST /distributions/{id}/items`, `PATCH /distributions/{id}/items/{item_id}`, `POST /distributions/{id}/send`, `POST /distributions/{id}/cancel`
  - Nested `GET /funds/{fund_id}/distributions` on the funds router
  - Mount under `/distributions`

- [ ] Implement allocation helpers:
  - Add `backend/app/services/allocation.py` exporting `allocate_pro_rata(total_amount: Decimal, commitments: list[Commitment]) -> list[tuple[Commitment, Decimal]]` that splits an amount proportionally to `committed_amount`, with the rounding remainder applied to the largest commitment so the sum reconciles exactly
  - Use this from `POST /capital-calls/{id}/items?mode=pro-rata` and `POST /distributions/{id}/items?mode=pro-rata` to auto-populate items for all approved commitments on the fund. Manual mode (default) accepts an explicit list

- [ ] Hook commitment totals into the line-item lifecycle:
  - On every create/update/delete of `capital_call_items` or `distribution_items`, call `commitment_repository.recompute_totals(commitment_id)` inside the same SQLAlchemy session before commit
  - Verify by writing a test that issues a payment and asserts the linked commitment's `called_amount` matches the sum of `amount_paid` across its items

- [ ] Add integration tests:
  - `backend/tests/test_capital_calls_api.py` — end-to-end: create call → add items → record partial payment → parent transitions to `partially_paid` → record remaining payment → parent flips to `paid` and commitment.called_amount equals total
  - `backend/tests/test_distributions_api.py` — analogous coverage including a pro-rata allocation case
  - `backend/tests/test_allocation_service.py` — pure-function tests for rounding and edge cases (single commitment, zero total, mismatched currencies are out of scope)

- [ ] Update the Dashboard overview to power the FundDetail page:
  - Add `commitments_total_amount`, `capital_calls_outstanding` (count of calls with status in `scheduled, sent, partially_paid`), `distributions_ytd_amount` (sum of paid distribution items in the current calendar year), respecting RBAC
  - Add `GET /funds/{fund_id}/overview` returning fund-level KPIs (committed, called, distributed, remaining commitment, IRR placeholder of `null` for now)

- [ ] Sync OpenAPI client and run gates:
  - Run `make openapi`, `make test`, `make lint` and fix any findings
