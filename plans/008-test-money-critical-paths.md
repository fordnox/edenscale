# Plan 008: Add tests to the two untested money-critical modules

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/services/payment_matching.py apps/backend/app/services/metrics.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW (adds tests only; no production code changes)
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: tests
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

Two modules decide numbers that fund managers act on, and neither has a single
test importing it.

**`payment_matching.py`** decides which LP's incoming wire pays which capital
call. Its scoring functions rank candidates, and the wizard presents the
top-ranked one as the default suggestion. An operator confirming that default
assigns real money. A silent change to a weight or a confidence threshold
re-ranks candidates and produces a *different* default — a reconciliation error
against real money, with no automated detector. The only current coverage is
incidental: one end-to-end test asserts the happy path completes, but nothing
pins the ranking, the tiers, or the cutoff.

**`fund_metrics_bulk` / `latest_fund_navs`** compute the TVPI/DPI/IRR/NAV shown
on the **funds list**, while the tested `fund_metrics` / `latest_fund_nav` serve
the **fund detail page**. The bulk versions re-implement the aggregation to
avoid N+1 queries. This is the classic bulk/single divergence setup: a fund can
show one TVPI in the list and a different one on its detail page, with the
existing metrics tests all passing. For a fund-administration product,
inconsistent performance figures between two screens undermine trust in every
other number on the page.

Verify the gap yourself before starting — both greps should return nothing:
```
grep -rln "payment_matching" apps/backend/tests/
grep -rln "fund_metrics_bulk\|latest_fund_navs" apps/backend/tests/
```

## Current state

`apps/backend/app/services/payment_matching.py` — the functions to test:
- `_name_score` (~line 56) — fuzzy investor-name match
- `_amount_score` (~line 81) — closeness of paid vs due amount
- `_confidence` (~line 94) — maps a combined score to a tier; **thresholds 0.75
  and 0.45**
- the weighted combination (~line 141) inside `suggest_matches`
- `_SCORE_FLOOR` — the cutoff below which a candidate is not suggested
- tie-breaking (~line 169)
- `_open_items` (~lines 36-40) — the collectible-status filter, which correctly
  includes `overdue`

Read the module in full before writing tests. Do **not** infer behavior from
this plan's line numbers — read the actual code and pin what it *does*, not what
you think it should do. These are characterization tests.

`apps/backend/app/services/metrics.py`:
- `fund_metrics` (~line 160) — single-fund, **tested**
- `fund_metrics_bulk` (~line 180) — list version, **untested**; guarantees an
  entry for every requested id (~line 185)
- `latest_fund_nav` (~line 251) — single, **tested**; orders by
  `as_of_date.desc(), created_at.desc()`
- `latest_fund_navs` (~line 262) — bulk, **untested**; orders by
  `fund_id, as_of_date.desc()` only — **note the missing `created_at`
  tiebreaker**, which is a real latent divergence (see step 4)
- both funnel through a shared `_build_metrics`

`apps/backend/tests/test_metrics_service.py` currently imports only
`fund_cashflows, fund_metrics, xirr` (line ~25) and `latest_fund_nav` (~line 26).

Test conventions: use the fixtures in `apps/backend/tests/conftest.py`. Model
DB-backed tests on `apps/backend/tests/test_metrics_service.py` and
`apps/backend/tests/test_bank_imports_api.py` (for seeding imports and
transactions).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| New tests | `cd apps/backend && uv run pytest tests/test_payment_matching.py tests/test_metrics_service.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |

## Scope

**In scope**:
- `apps/backend/tests/test_payment_matching.py` (create)
- `apps/backend/tests/test_metrics_service.py` (extend)

**Out of scope** (do NOT touch):
- `apps/backend/app/services/payment_matching.py` — **do not change production
  code.** If a test reveals what looks like a bug, that is a *finding to report*,
  not something to fix here. Characterize the current behavior, and say in your
  report what looked wrong.
- `apps/backend/app/services/metrics.py` — same rule, with one deliberate
  exception in step 4 which is a one-line ordering fix.
- Any other test file.

## Git workflow

- Branch: `advisor/008-test-money-paths`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Read the modules

Read `apps/backend/app/services/payment_matching.py` and the four metrics
functions in full. Write down the actual thresholds, weights, and cutoffs. Your
tests must assert what the code does today.

### Step 2: Unit-test the scoring functions

Create `apps/backend/tests/test_payment_matching.py`. Test the pure functions
directly (no DB needed) with a case table:

For `_name_score`: exact match; case-insensitive match; whitespace/punctuation
differences; a substring match; a completely unrelated name; empty/None input.

For `_amount_score`: exact amount; slight underpayment; slight overpayment;
gross mismatch; zero.

For `_confidence`: values on **both sides of each threshold, and exactly on
them** — 0.44 / 0.45 / 0.46 and 0.74 / 0.75 / 0.76. Boundary behavior is what
silently changes when someone "tidies" a comparison operator, so pin it
explicitly.

Use `Decimal` for money values throughout, matching the module.

**Verify**: `cd apps/backend && uv run pytest tests/test_payment_matching.py -v` → all pass.

### Step 3: Test `suggest_matches` ordering and the floor

Add DB-backed tests in the same file:

- Given a transaction and several open capital-call items, candidates come back
  in descending score order (assert the **order**, not just membership).
- A candidate scoring below `_SCORE_FLOOR` is not suggested at all.
- An item on a `paid` or `cancelled` call is not offered (per `_open_items`).
- An item on an `overdue` call **is** offered — this pins the behavior that
  currently disagrees with the dashboard (see plan 005).
- Tie-breaking is deterministic: two candidates with equal scores come back in a
  stable order across runs.

Seed data following `apps/backend/tests/test_bank_imports_api.py`.

**Verify**: `cd apps/backend && uv run pytest tests/test_payment_matching.py -v` → all pass.

### Step 4: Pin bulk metrics against single metrics

Extend `apps/backend/tests/test_metrics_service.py`:

- Seed 3 funds with differing commitments, calls, distributions, and NAV marks.
- Assert `fund_metrics_bulk(db, ids)[fid]` equals `fund_metrics(db, fid)` for
  **every** fund — field by field (`nav`, `dpi`, `tvpi`, `rvpi`, `irr`,
  `called`, `distributed`). This equivalence test is what makes the two
  implementations permanently unable to drift.
- `fund_metrics_bulk(db, [])` returns an empty mapping.
- `fund_metrics_bulk` with an unknown fund id returns an entry for it (the
  documented guarantee) — assert the shape it actually returns.
- `latest_fund_navs(db, ids)` matches `latest_fund_nav(db, fid)` per fund.

Then the **same-date case**: seed a fund with two `FundValuation` rows sharing
one `as_of_date` but different `created_at` and different NAV values. Assert
`latest_fund_navs` and `latest_fund_nav` agree.

This test will likely **fail**, because `latest_fund_navs` lacks the
`created_at.desc()` tiebreaker that `latest_fund_nav` has. If it fails, make the
**one-line fix**: add `FundValuation.created_at.desc()` to the bulk `order_by`.
This is the single permitted production change in this plan.

First check `FundValuationRepository.upsert` and the model's constraints: if a
unique constraint on `(fund_id, as_of_date)` makes same-date rows impossible,
then the divergence is unreachable — in that case **delete the same-date test**,
make no production change, and report which constraint rules it out.

**Verify**: `cd apps/backend && uv run pytest tests/test_metrics_service.py -v` → all pass.

## Test plan

Summarized above. The two highest-value assertions are the `_confidence`
boundary cases (step 2) and the bulk-vs-single equivalence (step 4).

Verification: `cd apps/backend && uv run pytest -q` → all pass, ~25 new tests.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `apps/backend/tests/test_payment_matching.py` exists and imports `app.services.payment_matching`
- [ ] `grep -rln "fund_metrics_bulk" apps/backend/tests/` returns a match
- [ ] Tests exist asserting `_confidence` behavior exactly at 0.45 and 0.75
- [ ] A field-by-field bulk-vs-single equivalence test exists for `fund_metrics_bulk`
- [ ] `git diff --stat apps/backend/app/` shows **either** no changes **or**
      exactly the one-line `order_by` fix from step 4
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- A characterization test reveals behavior that looks like a genuine bug (e.g. a
  threshold comparison that is inverted, or a name score that ranks an unrelated
  investor highest). **Report it — do not fix it.** A behavior change to the
  matching scorer needs a human decision, because it changes which LP gets
  matched to which payment.
- Making a test pass requires changing anything in
  `apps/backend/app/services/payment_matching.py`.
- The step-4 production change would need to be more than the single `order_by`
  line.
- The scoring functions turn out to be private in a way that makes direct
  testing awkward — report rather than refactoring the module for testability.

## Maintenance notes

- These are **characterization** tests: they lock in current behavior, including
  any warts. That is deliberate — they make future changes to the scorer
  *visible* rather than correct. If the team later decides a threshold is wrong,
  the test should be updated in the same commit as the change, with the
  reasoning in the message.
- The bulk-vs-single equivalence test is the durable one. Any future
  optimization of `fund_metrics_bulk` (and there is a pending one — see plan
  006's notes on the dashboard's per-fund loop) is safe precisely because this
  test exists.
- A reviewer should scrutinize: that the boundary tests assert *on* the
  threshold values and not merely around them, and that no production behavior
  changed apart from the permitted `order_by` line.
