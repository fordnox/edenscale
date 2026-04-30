# Phase 04: Backend — Capital Calls And Distributions

This phase builds the capital flow engine. Capital calls and distributions follow nearly identical patterns: a parent record tied to a fund, a status lifecycle (`draft → scheduled → sent → partially_paid → paid` or cancelled), and a set of line items that allocate amounts across active commitments. The crucial business rule: every time a line item changes paid amount, the parent's status and the linked commitment's running totals must be recomputed in the same transaction.

## Tasks

- [x] Read Phase 03's commitment repository, especially `recompute_totals`, before extending it; review the `capital_call`, `capital_call_item`, `distribution`, `distribution_item` model files from Phase 01 so the foreign keys and unique constraints are correct
  - Notes from review:
    - `CommitmentRepository.recompute_totals` (`backend/app/repositories/commitment_repository.py:113`) currently aggregates `CapitalCallItem.amount_due` into `called_amount` and `DistributionItem.amount_due` into `distributed_amount`. The Phase 04 test described later asserts `called_amount` equals the sum of `amount_paid` — that switch (or an `amount_paid`-based recompute) needs to land in the line-item-lifecycle task.
    - `CapitalCall` (`backend/app/models/capital_call.py`): fund_id FK → funds.id; status enum `CapitalCallStatus` (draft/scheduled/sent/partially_paid/paid/overdue/cancelled); has `due_date` (NOT NULL), `call_date` (NULL), `amount`, `created_by_user_id`. Relationship `items` → `CapitalCallItem`.
    - `CapitalCallItem` (`backend/app/models/capital_call_item.py`): unique constraint `uq_capital_call_item_call_commitment` on `(capital_call_id, commitment_id)` — bulk add must reject duplicates per call. `amount_paid` defaults to 0; `paid_at` nullable.
    - `Distribution` (`backend/app/models/distribution.py`): mirrors CapitalCall but uses `distribution_date` (NOT NULL) and `record_date` (NULL); status enum `DistributionStatus` lacks `overdue`.
    - `DistributionItem` (`backend/app/models/distribution_item.py`): unique constraint `uq_distribution_item_dist_commitment` on `(distribution_id, commitment_id)`; same `amount_due`/`amount_paid`/`paid_at` shape as `CapitalCallItem`.
    - `CommitmentRepository.list` already implements RBAC (admin all, fund_manager scoped to their org via `Fund.organization_id`, lp scoped via `InvestorContact`) — capital-call/distribution repositories should mirror that pattern, joining through the parent's fund or via `commitment` for LPs.

- [x] Implement Capital Calls:
  - `backend/app/schemas/capital_call.py` — `CapitalCallCreate` (fund_id, title, description, due_date, call_date, amount), `CapitalCallUpdate`, `CapitalCallRead` with nested `items: list[CapitalCallItemRead]` and `fund: FundSummary`, plus `CapitalCallItemCreate`/`Update`/`Read`
  - `backend/app/repositories/capital_call_repository.py` — `list_for_user(user, fund_id=None, status=None)` (RBAC: admin all; fund_manager org-scoped; lp only via their commitments → items), `get_with_items`, `create_draft`, `update`, `add_items` (bulk-insert allocations from a list of `(commitment_id, amount_due)` tuples; rejects when commitment.fund_id != call.fund_id), `set_item_payment(item_id, amount_paid, paid_at)`, `transition_status(call_id, new_status)` enforcing the lifecycle, `recompute_status(call_id)` that derives the parent status from item totals
  - `backend/app/routers/capital_calls.py` — `GET /capital-calls`, `GET /capital-calls/{id}`, `POST /capital-calls`, `PATCH /capital-calls/{id}`, `POST /capital-calls/{id}/items`, `PATCH /capital-calls/{id}/items/{item_id}` (records a payment; updates parent + commitment totals atomically), `POST /capital-calls/{id}/send` (transitions draft/scheduled → sent and stamps `call_date`), `POST /capital-calls/{id}/cancel`
  - Add nested route `GET /funds/{fund_id}/capital-calls` on the funds router for the FundDetail page
  - Mount under `/capital-calls`
  - Implementation notes:
    - Schemas: `CapitalCallCreate/Update/Read`, `CapitalCallItemCreate/Update/Read`, `CapitalCallItemBulkCreate`, and a small `CapitalCallFundSummary` for the embedded fund payload — non-negative validators on amounts, positive validator on parent `amount`.
    - Repository wires `CommitmentRepository.recompute_totals` into `add_items`, `set_item_payment`, and `update_item` so the linked commitments stay in sync. `recompute_status` derives `partially_paid` / `paid` from item totals while preserving `overdue` / pre-send statuses; `transition_status` enforces a strict draft → scheduled → sent → partially_paid → paid lifecycle with `cancelled` reachable from any non-terminal state.
    - Router uses `get_current_user_record` for visibility and `require_roles(admin, fund_manager)` for mutations; `_ensure_manager_can_edit` 403s when a fund_manager touches a fund outside their org. `add_items` translates `ValueError` (duplicates / cross-fund commitments) to 400, and `IntegrityError` (DB-level unique constraint) to 409.
    - `send` stamps `call_date = utcnow().date()` only when missing, mirroring the model's nullability.
    - Both `/capital-calls` and the nested `/funds/{fund_id}/capital-calls` routers are mounted in `app/main.py`.
    - `make openapi` regenerated `backend/openapi.json` and `frontend/src/lib/schema.d.ts` so the typed client picks up the new paths/schemas.

- [x] Implement Distributions (parallel to Capital Calls):
  - Schemas, repository, router mirror the capital call pattern — `Distribution` parent + `DistributionItem` line items
  - Endpoints: `GET /distributions`, `GET /distributions/{id}`, `POST /distributions`, `PATCH /distributions/{id}`, `POST /distributions/{id}/items`, `PATCH /distributions/{id}/items/{item_id}`, `POST /distributions/{id}/send`, `POST /distributions/{id}/cancel`
  - Nested `GET /funds/{fund_id}/distributions` on the funds router
  - Mount under `/distributions`
  - Implementation notes:
    - Schemas (`backend/app/schemas/distribution.py`): `DistributionCreate/Update/Read`, `DistributionItemCreate/Update/Read`, `DistributionItemBulkCreate`, `DistributionFundSummary` — same non-negative validators on item amounts and positive validator on parent `amount` as the capital-call shape, but using `distribution_date` (NOT NULL) and `record_date` (nullable) per the model.
    - Repository (`backend/app/repositories/distribution_repository.py`) wires `CommitmentRepository.recompute_totals` into `add_items`, `set_item_payment`, and `update_item`. `recompute_status` derives `partially_paid` / `paid` from item totals while preserving pre-send statuses; `transition_status` enforces `draft → scheduled → sent → partially_paid → paid` with `cancelled` reachable from any non-terminal state. `DistributionStatus` has no `overdue` value, so the lifecycle map omits it.
    - `send` stamps `record_date = utcnow().date()` only when missing (mirroring the model nullability — capital calls stamp `call_date`).
    - Router (`backend/app/routers/distributions.py`) reuses the same RBAC pattern: `get_current_user_record` for visibility, `require_roles(admin, fund_manager)` for mutations, `_ensure_manager_can_edit` 403s when a fund_manager touches a fund outside their org. `add_items` translates `ValueError` → 400 and `IntegrityError` → 409.
    - Both `/distributions` and the nested `/funds/{fund_id}/distributions` routers are mounted in `app/main.py`.
    - `make openapi` regenerated `backend/openapi.json` and `frontend/src/lib/schema.d.ts`. `make test` (45 tests) and `make lint` both pass.

- [x] Implement allocation helpers:
  - Add `backend/app/services/allocation.py` exporting `allocate_pro_rata(total_amount: Decimal, commitments: list[Commitment]) -> list[tuple[Commitment, Decimal]]` that splits an amount proportionally to `committed_amount`, with the rounding remainder applied to the largest commitment so the sum reconciles exactly
  - Use this from `POST /capital-calls/{id}/items?mode=pro-rata` and `POST /distributions/{id}/items?mode=pro-rata` to auto-populate items for all approved commitments on the fund. Manual mode (default) accepts an explicit list
  - Implementation notes:
    - `app/services/allocation.py` quantizes each share to two decimals with `ROUND_HALF_UP` (matching the `Numeric(18, 2)` columns) and sweeps the rounding remainder onto the commitment with the largest `committed_amount` so the per-share sum reconciles exactly with the input total. Edge cases: empty commitment list returns `[]`, zero total returns `0.00` shares, total committed of zero raises `ValueError` so the caller can surface a 400.
    - Routers added a `mode: Literal["manual", "pro-rata"] = Query("manual")` query param. `pro-rata` loads `Commitment.status == approved` rows on the parent's fund, calls `allocate_pro_rata(parent.amount, ...)`, and routes the resulting `(commitment_id, amount)` tuples through the existing `repo.add_items` path so duplicate-allocation and cross-fund safeguards still apply. Manual mode is unchanged. No approved commitments → 400.
    - `make openapi`, `make test` (45 passing), and `make lint` all clean. Frontend `schema.d.ts` regenerated to include the `mode` query parameter on both endpoints.

- [x] Hook commitment totals into the line-item lifecycle:
  - On every create/update/delete of `capital_call_items` or `distribution_items`, call `commitment_repository.recompute_totals(commitment_id)` inside the same SQLAlchemy session before commit
  - Verify by writing a test that issues a payment and asserts the linked commitment's `called_amount` matches the sum of `amount_paid` across its items
  - Implementation notes:
    - `CommitmentRepository.recompute_totals` now aggregates `CapitalCallItem.amount_paid` into `called_amount` and `DistributionItem.amount_paid` into `distributed_amount` (was `amount_due`). This is the right ledger semantic — `called` = cash received, not cash owed — and it's what the next test asserts.
    - Switched `recompute_totals` from `commit()`+`refresh()` to `flush()` only. Both call sites (`CapitalCallRepository.add_items` / `set_item_payment` / `update_item` and the parallel distribution methods) already commit afterward, so the recompute now lands in the same transaction as the line-item write. No other callers exist.
    - Tests live in `backend/tests/test_commitments_api.py::TestRecomputeTotalsLifecycle`: one for capital calls (partial → full payment, plus a sibling commitment that must stay at zero) and one for distributions. Both assert `commitment.called_amount` (resp. `distributed_amount`) equals `sum(amount_paid)` across the commitment's items.
    - `make test` (47 tests) and `make lint` clean. `make openapi` produced no diff since the change was internal.
    - Note: there is no `delete` operation on capital-call/distribution items in the repository or routers today, so the lifecycle hook only had to cover create + update. If a delete endpoint is added later it must call `recompute_totals` before commit on the same session.

- [x] Add integration tests:
  - `backend/tests/test_capital_calls_api.py` — end-to-end: create call → add items → record partial payment → parent transitions to `partially_paid` → record remaining payment → parent flips to `paid` and commitment.called_amount equals total
  - `backend/tests/test_distributions_api.py` — analogous coverage including a pro-rata allocation case
  - `backend/tests/test_allocation_service.py` — pure-function tests for rounding and edge cases (single commitment, zero total, mismatched currencies are out of scope)
  - Implementation notes:
    - `test_capital_calls_api.py` (12 tests): full lifecycle (draft → items → send → partial pay → fully paid) asserting `commitment.called_amount` equals `sum(amount_paid)` at each step, plus a parallel-LP scenario where one of two LPs pays in full and the call stays `partially_paid`. Validation: zero amount → 422, unknown fund → 404, cross-fund commitment → 400, duplicate allocation → 400. Lifecycle: `cancel` from draft, `/send` rejected once `paid`. RBAC: lp cannot create (403), fund_manager cannot touch other-org fund (403), lp listing only surfaces calls with their own commitments. Plus the nested `GET /funds/{fund_id}/capital-calls` route.
    - `test_distributions_api.py` (8 tests): mirror lifecycle assertion against `commitment.distributed_amount`. Pro-rata case posts to `/distributions/{id}/items?mode=pro-rata` with one approved 750/250 split + a pending commitment that must be excluded — asserts shares are 75.00/25.00 and pending LP is skipped. `mode=pro-rata` with no approved commitments → 400. Same RBAC + nested-fund coverage as capital calls.
    - `test_allocation_service.py` (11 tests): empty list → `[]`, zero total → all-zero shares, negative total → `ValueError`, zero total committed → `ValueError`, single commitment → full amount, even split, uneven split, three-way split with rounding remainder swept onto the largest weight, sum reconciles exactly to two decimals.
    - `make test` (78 tests passing) and `make lint` clean. `make openapi` produced no diff since these are tests only.

- [ ] Update the Dashboard overview to power the FundDetail page:
  - Add `commitments_total_amount`, `capital_calls_outstanding` (count of calls with status in `scheduled, sent, partially_paid`), `distributions_ytd_amount` (sum of paid distribution items in the current calendar year), respecting RBAC
  - Add `GET /funds/{fund_id}/overview` returning fund-level KPIs (committed, called, distributed, remaining commitment, IRR placeholder of `null` for now)

- [ ] Sync OpenAPI client and run gates:
  - Run `make openapi`, `make test`, `make lint` and fix any findings
