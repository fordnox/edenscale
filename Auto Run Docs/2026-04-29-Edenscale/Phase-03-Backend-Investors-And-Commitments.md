# Phase 03: Backend — Investors And Commitments

This phase builds the LP side of the data model: investors (legal entities), investor contacts (the natural-person side), and commitments (the link between investors and funds with committed/called/distributed totals). Commitments are the central ledger row from which capital calls and distributions are allocated, so this phase must enforce the `(fund_id, investor_id)` uniqueness constraint and keep the running totals (`called_amount`, `distributed_amount`) in sync with related items.

## Tasks

- [ ] Read the Phase 01 models for `Investor`, `InvestorContact`, and `Commitment` and the Phase 02 RBAC dependency, repository, and router patterns; reuse them rather than introducing a new style

- [ ] Implement Investors:
  - `backend/app/schemas/investor.py` — `InvestorCreate`, `InvestorUpdate`, `InvestorRead`, `InvestorListItem` with `total_committed` and `fund_count` aggregate fields (computed at read time)
  - `backend/app/repositories/investor_repository.py` — `list_for_user(user)` (admin: all; fund_manager: org-scoped; lp: only investors that the caller's investor_contact rows reference), `get`, `create`, `update`, `delete` (hard delete only if no commitments exist; otherwise raise a 409)
  - `backend/app/routers/investors.py` — `GET /investors`, `GET /investors/{id}`, `POST /investors` (fund_manager+admin), `PATCH /investors/{id}`, `DELETE /investors/{id}`
  - Mount under `/investors`

- [ ] Implement Investor Contacts:
  - Schemas/repository/router with endpoints `GET /investors/{investor_id}/contacts`, `POST /investors/{investor_id}/contacts`, `PATCH /investors/{investor_id}/contacts/{contact_id}`, `DELETE /investors/{investor_id}/contacts/{contact_id}`
  - Enforce the rule that an investor has exactly one `is_primary=True` contact: when a contact is set primary, set all sibling contacts to `is_primary=False` in the same transaction
  - Allow LPs to read their own contact rows (those whose `user_id` matches the local User record); editing requires fund_manager+admin

- [ ] Implement Commitments:
  - `backend/app/schemas/commitment.py` — `CommitmentCreate`, `CommitmentUpdate`, `CommitmentRead` with `committed_amount`, `called_amount`, `distributed_amount`, `commitment_date`, `status`, `share_class`, `notes`, plus nested `fund: FundSummary` and `investor: InvestorSummary` for read responses
  - `backend/app/repositories/commitment_repository.py` — `list(filter_by_fund=None, filter_by_investor=None, user=...)` with the same RBAC visibility rules used for funds/investors, `get`, `create` (rejects with 409 if `(fund_id, investor_id)` already exists), `update`, `set_status`, `recompute_totals(commitment_id)` that recalculates `called_amount` and `distributed_amount` from related capital_call_items and distribution_items (will be exercised in Phase 04 but stub the method now so it can be called when items are created)
  - `backend/app/routers/commitments.py` — `GET /commitments`, `GET /commitments/{id}`, `POST /commitments`, `PATCH /commitments/{id}`, `POST /commitments/{id}/status` (approve/decline/cancel)
  - Add convenience routes nested under funds and investors: `GET /funds/{fund_id}/commitments`, `GET /investors/{investor_id}/commitments`
  - Mount under `/commitments`, and register the nested routes in their respective routers

- [ ] Add validation at the schema and DB level:
  - Pydantic validators on `committed_amount > 0`, `called_amount <= committed_amount`, `distributed_amount` not bounded by committed (distributions can exceed contributions in private funds — leave it unconstrained but document the choice in a `# Why:` comment)
  - DB-level: confirm the `UniqueConstraint("fund_id", "investor_id")` from the Phase 01 model is reflected in the migration — if not, add a follow-up Alembic migration

- [ ] Add integration tests:
  - `backend/tests/test_investors_api.py` — fund_manager creates an investor + 2 contacts, primary flag flips correctly when reassigned, delete with commitments returns 409
  - `backend/tests/test_commitments_api.py` — fund_manager creates a commitment, duplicate `(fund_id, investor_id)` returns 409, status transitions validated, LP can read their own commitments via `GET /investors/{id}/commitments`

- [ ] Wire the new totals into the Dashboard overview:
  - Update `backend/app/routers/dashboard.py` and the `/dashboard/overview` aggregates so `investors_total` and `commitments_total_amount` are sourced from the new tables and respect the caller's RBAC scope
  - Update `backend/tests/` to cover the dashboard with seeded data

- [ ] Sync OpenAPI client and run gates:
  - Run `make openapi`, `make test`, `make lint` and resolve issues
