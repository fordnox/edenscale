# Plan 016: Scope aggregates to the tenant, batch eager loads, and bound unbounded lists

> **Executor instructions**: Follow step by step. Run every verification command.
> If a STOP condition occurs, stop and report — do not improvise.
>
> **Drift check**: `git diff --stat HEAD -- apps/backend/app/repositories apps/backend/app/routers/superadmin.py apps/backend/app/routers/fund_valuations.py`

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (touches list endpoints the superadmin UI consumes)
- **Depends on**: none
- **Category**: perf
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21

## Why this matters

Four query-shape problems, ordered by how badly they degrade as the platform
grows:

**(a) Tenant-wide aggregate scans.** `investor_repository._base_query()` builds a
subquery that groups **every commitment row on the platform** with no `WHERE`,
then filters by `organization_id` in the *outer* query. Cost grows with total
platform data rather than the requesting tenant's data — the classic
multi-tenant scaling cliff. `dashboard_repository` has the same shape.

**(b) `joinedload` on to-many collections.** Joined eager loading multiplies
parent rows by child rows on the wire; SQLAlchemy then de-duplicates in Python.
A 100-call page where each call has 200 items transfers 20,000 rows with every
parent column repeated. `selectinload` issues one extra `IN (...)` query and
transfers each row once.

**(c) Unbounded list endpoints.** Four routes have no `skip`/`limit`.
`list_all_users` is the sharpest: `UserRead` nests memberships and their
organizations, so response size grows superlinearly and it becomes the slowest
endpoint on the system exactly when the business succeeds.

**(d) A per-fund metrics loop** on the dashboard where a purpose-built batch
function already exists and is already used correctly elsewhere.

Honest framing: (a) and (c) are about *future* scale; (b) and (d) are modest
today. None is an outage. This is preventive work on the paths most likely to
degrade.

## Current state

`apps/backend/app/repositories/investor_repository.py:23-38` — `_base_query()`
groups `Commitment` with no tenant predicate; the org filter appears at ~line 47
in `list_for_membership`.

`apps/backend/app/repositories/dashboard_repository.py:235-253` — `fund_agg_subq`
has the same shape; scoping is applied afterwards via `_scope_by_fund`.

`apps/backend/app/repositories/dashboard_repository.py` ~line 261-265 — a loop
over at most 5 recent funds calling `fund_metrics(db, fund.id)` per fund. The
code self-documents this as a "bounded N+1". `fund_metrics_bulk` in
`app/services/metrics.py` (~line 180) is a drop-in and guarantees an entry for
every requested id; `apps/backend/app/routers/funds.py:87` already uses it.

`joinedload` on to-many relationships:
- `capital_call_repository.py:60` — `joinedload(CapitalCall.items)`, on the base
  query all list calls use, combined with `.offset(...).limit(...)`
- `distribution_repository.py:53` — `joinedload(Distribution.items)`
- `communication_repository.py:31` — `joinedload(Communication.recipients)`
- `bank_import_repository.py:79` — `joinedload(BankStatementImport.transactions)`

Keep `joinedload` for **to-one** relationships (`CapitalCall.fund`,
`Distribution.fund`, `Document.fund`/`.investor`) — those are correct as-is.

Unbounded routes:
- `apps/backend/app/routers/superadmin.py` — `list_all_organizations` (~line 77),
  `list_all_users` (~line 139, docstring says it returns every user on the
  platform), `list_organization_members` (~line 344)
- `apps/backend/app/routers/fund_valuations.py:36` — `list_fund_valuations`
- `apps/backend/app/routers/users.py:57` — `list_my_memberships` is also
  unbounded but naturally small; **leave it alone**.

Every other list route in the codebase takes `skip`/`limit` with a default of
100 — match that convention exactly.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `cd apps/backend && uv run pytest -q` | `456 passed` + new, 0 failed |
| Lint | `make lint` (repo root) | exit 0 |
| Regenerate client | `make openapi` | exit 0; schema updated for new query params |
| Frontend typecheck | `pnpm turbo run typecheck` | 7/7 |

Environment (both): `export APP_DOMAIN=localhost` and an isolated
`APP_DATABASE_DSN` (suffix `_wt016`). Never print the DSN.

## Scope

**In scope**:
- `apps/backend/app/repositories/investor_repository.py`, `dashboard_repository.py`,
  `capital_call_repository.py`, `distribution_repository.py`,
  `communication_repository.py`, `bank_import_repository.py`
- `apps/backend/app/routers/superadmin.py`, `fund_valuations.py`
- `apps/backend/tests/` — the corresponding test modules
- `apps/backend/openapi.json`, `packages/api/src/schema.d.ts` (via `make openapi` only)
- `apps/superadmin/src/**` — only if step 3 requires paging the UI

**Out of scope**:
- `app/services/metrics.py` internals — `fund_metrics_bulk` is correct and now
  has an equivalence test (plan 008). Call it; don't change it.
- `app/routers/users.py::list_my_memberships`.
- Converting `joinedload` on to-one relationships.
- Adding database indexes — a separate concern needing migration review.

## Steps

### Step 1: Scope the aggregate subqueries to the tenant

In `investor_repository._base_query()`, push the organization predicate **inside**
the subquery (join `Investor` within the subquery and filter on
`organization_id`) rather than relying on the outer join to discard rows.
`_base_query()` currently takes no arguments — it will need the scoping value
threaded in; keep the change minimal and preserve the existing call sites'
behavior.

Do the same for `dashboard_repository`'s `fund_agg_subq`.

**Results must not change** — the outer filter already constrains the same rows.
The existing list tests are your safety net.

**Measure before claiming a win**: run `EXPLAIN ANALYZE` on the before and after
queries against a seeded database, and report both. PostgreSQL may already push
the predicate down, in which case this is a no-op and you should say so plainly
rather than asserting an improvement you did not observe.

**Verify**: `cd apps/backend && uv run pytest tests/test_investors_api.py tests/test_dashboard.py -v` → all pass.

### Step 2: Swap `joinedload` → `selectinload` on the four to-many relationships

Four import-and-call-site changes at the lines listed above. `selectinload` is
semantically equivalent for these relationships and adds one query per
collection.

**Verify**: `cd apps/backend && uv run pytest tests/test_capital_calls_api.py tests/test_distributions_api.py tests/test_communications_api.py tests/test_bank_imports_api.py -v` → all pass.

### Step 3: Add pagination to the four unbounded routes

Add `skip: int = 0, limit: int = 100` to the three superadmin routes and
`list_fund_valuations`, threading through to the repositories (which mostly
accept these already in analogous methods).

**This is the risky step.** Any `apps/superadmin` client assuming a complete
list will silently truncate. Two mitigations, both required:
- ship a generous default (use 100 to match the house convention, but if a
  superadmin screen genuinely needs more, raise *that route's* default and say
  which),
- **check the superadmin UI** for each affected endpoint and update it to page,
  or at minimum to request an explicit limit. Grep
  `apps/superadmin/src` for the call sites.

Add a `has_more` flag or total count if the UI needs one to page — say what you
chose.

Then run `make openapi` (route signatures changed) and `pnpm turbo run typecheck`.

**Verify**: `make openapi` exits 0; `pnpm turbo run typecheck` → 7/7.

### Step 4: Use the batch metrics function on the dashboard

Hoist `metrics_by_fund = fund_metrics_bulk(db, [f.id for f, _, _ in fund_rows])`
above the loop in `dashboard_repository` and index into it. Remove the now-stale
"Bounded N+1" comment.

**Verify**: `cd apps/backend && uv run pytest tests/test_dashboard.py -v` → all pass.

### Step 5: Tests

- Investor list and dashboard return identical results before/after step 1
  (the existing tests cover this — confirm they pass unmodified).
- Each newly-paginated route respects `skip`/`limit` and returns the documented
  default when they are omitted.
- The dashboard's recent-funds metrics match what `fund_metrics` returns per
  fund (guards step 4 against the bulk/single divergence plan 008 tested for).

**Verify**: `cd apps/backend && uv run pytest -q` → all pass.

## Done criteria

- [ ] `cd apps/backend && uv run pytest -q` → 0 failures
- [ ] `make lint` → exit 0
- [ ] `make openapi` run; regenerated files included in the diff
- [ ] `pnpm turbo run typecheck` → 7/7
- [ ] `grep -n "joinedload" apps/backend/app/repositories/*.py` shows no to-many collections
- [ ] The four routes accept `skip`/`limit`
- [ ] `EXPLAIN ANALYZE` before/after reported for step 1, with an honest verdict
- [ ] No existing test's expected result changed
- [ ] `git diff --name-only` contains no file outside the in-scope list

## STOP conditions

- Step 1 changes any query result — revert and report.
- `EXPLAIN ANALYZE` shows the planner already pushed the predicate down and the
  rewrite makes the plan *worse* — report and revert that part; a no-op change
  that complicates the query is not worth keeping.
- Paginating a superadmin route breaks its UI in a way that needs more than a
  small change — report rather than rewriting the screen.
- Threading scoping into `_base_query()` requires changing its call-site
  contract in more than a couple of places.

## Maintenance notes

- If pagination is added to a route later, re-check any `selectinload` on that
  path — the extra `IN (...)` query is per-page, which is the point.
- The four newly-paginated routes now have a default that silently caps results.
  That is a behavior change for API consumers; note it if anything external
  consumes them.
- Deliberately deferred: index additions implied by these query patterns
  (especially a functional index for the case-insensitive contact-email lookup
  in `investor_contact_repository.py`). Those need migration review and
  `CREATE INDEX CONCURRENTLY` on a live table.
