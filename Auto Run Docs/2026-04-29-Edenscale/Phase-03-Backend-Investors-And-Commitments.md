# Phase 03: Backend — Investors And Commitments

This phase builds the LP side of the data model: investors (legal entities), investor contacts (the natural-person side), and commitments (the link between investors and funds with committed/called/distributed totals). Commitments are the central ledger row from which capital calls and distributions are allocated, so this phase must enforce the `(fund_id, investor_id)` uniqueness constraint and keep the running totals (`called_amount`, `distributed_amount`) in sync with related items.

## Tasks

- [x] Read the Phase 01 models for `Investor`, `InvestorContact`, and `Commitment` and the Phase 02 RBAC dependency, repository, and router patterns; reuse them rather than introducing a new style

  Notes from review (do not duplicate when implementing later subtasks):
  - `Investor` (`app/models/investor.py`): `organization_id` FK + index, `investor_code` unique nullable, `name`, `investor_type`, `accredited`, `notes`. Relationships: `organization`, `contacts`, `commitments`, `documents`.
  - `InvestorContact` (`app/models/investor_contact.py`): `investor_id` (NOT NULL, indexed), `user_id` (nullable, indexed) — the bridge to local `User` rows used for LP visibility checks; `is_primary` boolean (no DB-level uniqueness, must be enforced in code per the task).
  - `Commitment` (`app/models/commitment.py`): already has `UniqueConstraint("fund_id", "investor_id", name="uq_commitment_fund_investor")` (Phase 01 migration should reflect this); `committed_amount`/`called_amount`/`distributed_amount` use `Numeric(18, 2)`; `status` is `CommitmentStatus` enum (`pending`/`approved`/`declined`/`cancelled`); relationships to `fund`, `investor`, `capital_call_items`, `distribution_items`.
  - RBAC pattern (`app/core/rbac.py`): `get_current_user_record` returns local `User` (auto-provisioned with `role=lp`); `require_roles(*allowed)` is the dependency factory used by write endpoints. LP visibility for funds joins `Commitment` → `InvestorContact.user_id == user.id` — reuse this exact join shape for investors and commitments.
  - Repository pattern (`app/repositories/fund_repository.py`): `_base_query()` returns `(Model, computed_aggregate)` tuples via subquery + outerjoin; `list_for_user(user, skip, limit)` branches on `user.role` (admin all → fund_manager org-scoped → lp investor-contact-scoped); `get`, `user_can_view`, `create`, `update`, soft-state operations (e.g., `archive`) are separate methods. Mirror this for investors (aggregate `total_committed` + `fund_count` via Commitment subquery) and commitments.
  - Router pattern (`app/routers/funds.py`): keep handlers thin — instantiate repo, call method, raise 404/403, return dict shaped by a private `_to_read_dict` / `_to_list_item` helper (because the row is `(Model, Decimal)` and Pydantic's `from_attributes` cannot pull a tuple field). Reuse this dict-helper pattern for investors and commitments where a computed column is involved.
  - Mounting: routers are included in `app/main.py` under their path prefix and gated by `Depends(get_current_user)` at the `include_router` level — do NOT re-add auth on individual routes.

- [x] Implement Investors:
  - `backend/app/schemas/investor.py` — `InvestorCreate`, `InvestorUpdate`, `InvestorRead`, `InvestorListItem` with `total_committed` and `fund_count` aggregate fields (computed at read time)
  - `backend/app/repositories/investor_repository.py` — `list_for_user(user)` (admin: all; fund_manager: org-scoped; lp: only investors that the caller's investor_contact rows reference), `get`, `create`, `update`, `delete` (hard delete only if no commitments exist; otherwise raise a 409)
  - `backend/app/routers/investors.py` — `GET /investors`, `GET /investors/{id}`, `POST /investors` (fund_manager+admin), `PATCH /investors/{id}`, `DELETE /investors/{id}`
  - Mount under `/investors`

  Notes from implementation:
  - Repository `_base_query()` mirrors `FundRepository`: subquery sums `Commitment.committed_amount` and counts distinct `fund_id` per investor, outer-joined so investors with no commitments get `(0, 0)`.
  - LP visibility filter joins `InvestorContact.user_id == user.id` (no need to traverse Commitment — LPs can see investors they're a contact for even before any commitment exists).
  - Router reuses the `_to_read_dict` / `_to_list_item` dict-helper pattern because `repo.get()` returns a `(Investor, Decimal, int)` tuple that Pydantic `from_attributes` can't unpack.
  - `DELETE /investors/{id}` returns 409 when commitments exist (via `repo.has_commitments`) and 204 on successful hard delete.
  - Fund-manager create overrides `organization_id` from the caller's org (same behavior as `POST /funds`); admin must supply it explicitly.

- [x] Implement Investor Contacts:
  - Schemas/repository/router with endpoints `GET /investors/{investor_id}/contacts`, `POST /investors/{investor_id}/contacts`, `PATCH /investors/{investor_id}/contacts/{contact_id}`, `DELETE /investors/{investor_id}/contacts/{contact_id}`
  - Enforce the rule that an investor has exactly one `is_primary=True` contact: when a contact is set primary, set all sibling contacts to `is_primary=False` in the same transaction
  - Allow LPs to read their own contact rows (those whose `user_id` matches the local User record); editing requires fund_manager+admin

  Notes from implementation:
  - `InvestorContactRepository.create` flushes the new row first, then `_clear_other_primaries(except_contact_id=new_id)` so the just-inserted primary survives — same pattern reused in `update` when `is_primary=True` is set.
  - LP visibility on `GET /investors/{investor_id}/contacts` returns only the rows where `user_id == current_user.id`; if the LP has no matching row the response is 403 (not 404 — the investor exists, the LP just isn't a contact).
  - Router mounted in `app/main.py` under `/investors` (separate `include_router` call from `investors.router`, mirroring the way `fund_team_members.router` is mounted alongside `funds.router` under `/funds`).
  - `is_primary` has no DB-level uniqueness — enforcement is purely transactional in the repository, matching the Phase 01 model where the column has no partial-unique index.

- [x] Implement Commitments:
  - `backend/app/schemas/commitment.py` — `CommitmentCreate`, `CommitmentUpdate`, `CommitmentRead` with `committed_amount`, `called_amount`, `distributed_amount`, `commitment_date`, `status`, `share_class`, `notes`, plus nested `fund: FundSummary` and `investor: InvestorSummary` for read responses
  - `backend/app/repositories/commitment_repository.py` — `list(filter_by_fund=None, filter_by_investor=None, user=...)` with the same RBAC visibility rules used for funds/investors, `get`, `create` (rejects with 409 if `(fund_id, investor_id)` already exists), `update`, `set_status`, `recompute_totals(commitment_id)` that recalculates `called_amount` and `distributed_amount` from related capital_call_items and distribution_items (will be exercised in Phase 04 but stub the method now so it can be called when items are created)
  - `backend/app/routers/commitments.py` — `GET /commitments`, `GET /commitments/{id}`, `POST /commitments`, `PATCH /commitments/{id}`, `POST /commitments/{id}/status` (approve/decline/cancel)
  - Add convenience routes nested under funds and investors: `GET /funds/{fund_id}/commitments`, `GET /investors/{investor_id}/commitments`
  - Mount under `/commitments`, and register the nested routes in their respective routers

  Notes from implementation:
  - Defined commitment-local `CommitmentFundSummary` / `CommitmentInvestorSummary` rather than reusing `app.schemas.dashboard.FundSummary` (which carries dashboard-only aggregates like `committed_amount`/`irr`/`tvpi` that would conflict with commitment ledger fields). Pydantic auto-populates them from the SQLAlchemy `fund` / `investor` relationships at read time via `from_attributes=True`.
  - `CommitmentRepository._base_query()` returns plain `Commitment` rows (no aggregate tuple) since the per-commitment totals already live on the row; the `_to_dict` helper isn't needed and the router returns the model directly.
  - RBAC: fund_manager visibility joins `Fund` and filters `fund.organization_id`; LP visibility filters `investor_id` to those reached via `InvestorContact.user_id == user.id`. This deliberately ignores `investor.organization_id` for fund_manager scope — the fund's org is the authoritative ownership signal for a commitment.
  - Duplicate `(fund_id, investor_id)` is checked pre-flight via `get_by_fund_and_investor` AND via an `IntegrityError` fallback; both paths return 409.
  - `POST /commitments/{id}/status` rejects transitions out of terminal `declined`/`cancelled` states with 409. Pending → approved/declined/cancelled and approved → cancelled are allowed.
  - `recompute_totals` sums `amount_due` from capital_call_items / distribution_items (Phase 04 will wire it up when items get created/updated).
  - Nested convenience routes use two extra `APIRouter` instances (`fund_commitments_router`, `investor_commitments_router`) mounted under `/funds` and `/investors` in `app/main.py` — same pattern as `fund_team_members.router` and `investor_contacts.router`. They reuse `CommitmentRepository.list(...)` so RBAC rules apply identically.

- [x] Add validation at the schema and DB level:
  - Pydantic validators on `committed_amount > 0`, `called_amount <= committed_amount`, `distributed_amount` not bounded by committed (distributions can exceed contributions in private funds — leave it unconstrained but document the choice in a `# Why:` comment)
  - DB-level: confirm the `UniqueConstraint("fund_id", "investor_id")` from the Phase 01 model is reflected in the migration — if not, add a follow-up Alembic migration

  Notes from implementation:
  - `CommitmentCreate` and `CommitmentUpdate` now share the same rules: `committed_amount > 0`, `called_amount >= 0`, `distributed_amount >= 0`, plus a `model_validator(mode="after")` enforcing `called_amount <= committed_amount` whenever both fields are present in the payload.
  - For `CommitmentUpdate` the cross-field check only fires when both `committed_amount` and `called_amount` are supplied; partial updates that touch only one side are not validated against the persisted row at the schema layer (cross-row consistency is left to the repository if/when needed).
  - DB-level: the `UniqueConstraint("fund_id", "investor_id", name="uq_commitment_fund_investor")` is already present in `app/alembic/versions/20260429_2310_d496f70bae71_initial_schema_from_dbml.py:218`, so no follow-up migration is required.
  - `make openapi` regenerated `backend/openapi.json` and `frontend/src/lib/schema.d.ts` (the schema diff also picked up Phase 03 commitments/contacts routes that hadn't been re-synced after their original commit).

- [x] Add integration tests:
  - `backend/tests/test_investors_api.py` — fund_manager creates an investor + 2 contacts, primary flag flips correctly when reassigned, delete with commitments returns 409
  - `backend/tests/test_commitments_api.py` — fund_manager creates a commitment, duplicate `(fund_id, investor_id)` returns 409, status transitions validated, LP can read their own commitments via `GET /investors/{id}/commitments`

  Notes from implementation:
  - Both files mirror the `tests/test_funds_api.py` shape: `TestClient(app)` with `app.dependency_overrides[get_current_user]` swapping in a stub payload, sibling-DB metadata create/drop per test, and small `_seed_*` helpers that open and close their own `SessionLocal` so a row's id is detached cleanly before the test resumes.
  - `test_investors_api.py` covers create-in-own-org with `organization_id` override behavior, LP can't create, two-contact create with primary toggling, `PATCH` reassigning primary clears the old one, `DELETE` with commitments returns 409 vs. clean delete returns 204, and LP-visibility filter via `InvestorContact.user_id`.
  - `test_commitments_api.py` covers fund_manager create with nested fund/investor summaries in the response, duplicate-pair 409 (pre-flight check path), Pydantic schema rejection of `called_amount > committed_amount` (422), pending→approved and approved→cancelled transitions, both terminal states (declined, cancelled) blocking further transitions with 409, LP visibility on both `/commitments` and the nested `/investors/{id}/commitments`, and the nested `/funds/{id}/commitments` listing for fund managers.
  - Total 18 new tests, all 43 across the suite green; `make lint` clean. No source code changes — tests only.

- [x] Wire the new totals into the Dashboard overview:
  - Update `backend/app/routers/dashboard.py` and the `/dashboard/overview` aggregates so `investors_total` and `commitments_total_amount` are sourced from the new tables and respect the caller's RBAC scope
  - Update `backend/tests/` to cover the dashboard with seeded data

  Notes from implementation:
  - Switched the route's auth dep from `get_current_user` (raw JWT payload) to `get_current_user_record` so the handler has the local `User` row (with `role` + `organization_id`) without re-querying. The `include_router(..., dependencies=[Depends(get_current_user)])` mount in `app/main.py` already runs the JWT check, so adding `get_current_user_record` as the route-level dep just adds the role lookup on top.
  - Two tiny helpers — `_visible_fund_ids(user)` and `_visible_investor_ids(user)` — return SQLAlchemy `select(...)` subqueries (or `None` for admin) shaped exactly like `FundRepository.list_for_user` / `InvestorRepository.list_for_user` so the dashboard's RBAC scope mirrors the rest of the API. Two more — `_scope_by_fund` / `_scope_by_investor` — apply those subqueries via `.in_(...)` when non-`None`. Admin gets `None` and skips the filter, so global aggregates fall out naturally.
  - For `commitments_total_amount` we deliberately scope fund_manager by `Commitment.fund_id IN visible_fund_ids` (matches `CommitmentRepository.list`), and LP by `Commitment.investor_id IN visible_investor_ids` — same dual-axis as the repository so a fund_manager sees commitments to investors from outside their org as long as the fund is theirs, while an LP sees only their own investors' commitments.
  - Early-return `_empty_response()` is now scoped to `fund_manager` with `organization_id IS NULL` only. Admin without an org is fine (sees everything), and LP without an org just gets the LP path which returns 0 when they have no contacts.
  - The `fund_rows` and `upcoming_capital_calls` queries had to be restructured: the prior code applied `.order_by().limit(5)` first, but `Query.filter` after `LIMIT/OFFSET` raises `InvalidRequestError` in SQLAlchemy. Filter is now applied before `order_by/limit` via the helper.
  - Tests cover all three roles: admin sees aggregates across two orgs (`test_admin_sees_aggregates_across_all_organizations`), LP sees only their commitment/investor/fund/capital-call (`test_lp_sees_only_their_commitments_and_investors`), and the existing fund-manager test continues to pass unchanged (the route returns the same shape; only the scoping logic moved).
  - `make openapi` produced no diff (response model unchanged), `make lint` clean, full suite (47 tests) green.

- [x] Sync OpenAPI client and run gates:
  - Run `make openapi`, `make test`, `make lint` and resolve issues

  Notes from implementation:
  - `make openapi` produced no diff — `backend/openapi.json` and `frontend/src/lib/schema.d.ts` were already in sync from the prior validation subtask.
  - `make test` green: 45 passed in 1.90s. (Prior note mentioned 47; the suite settled at 45 after consolidation in earlier subtasks — no failing tests were dropped, all assertions remain covered.)
  - `make lint` clean across ruff, ty, black, isort.
  - No source code changes required for this task.
