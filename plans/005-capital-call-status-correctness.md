# Plan 005: Stop overdue calls vanishing from dashboards, and gate allocations on closed calls

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/repositories/dashboard_repository.py apps/backend/app/repositories/capital_call_repository.py apps/backend/app/repositories/distribution_repository.py apps/backend/app/routers/capital_calls.py apps/backend/app/routers/distributions.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: bug
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

Two related defects in capital-call status handling, both of which hide money
that is owed.

**(a) Overdue calls disappear from every dashboard.** The dashboard's definition
of "outstanding" omits the `overdue` status. A daily cron flips past-due calls
from `sent`/`partially_paid` to `overdue` — so the morning after a call goes
past due, it drops out of both the outstanding count and the "upcoming capital
calls" panel, on manager *and* LP dashboards. The calls that most need chasing
are exactly the ones that become invisible. Note that `payment_matching`
correctly treats `overdue` as collectible, so two modules currently disagree
about what an outstanding call is.

**(b) Allocations can be added to closed calls.** `add_items` checks only that
the call exists. Adding an allocation to a fully-`paid` call raises `total_due`
above `total_paid` while the row still reads `paid` — so it never reappears on
the outstanding dashboard (compounding (a)), and `payment_matching`'s
collectible filter skips it, meaning the new LP's incoming wire can never be
matched from a bank statement. Adding items to a `cancelled` call inflates
committed/called aggregates for a call that was explicitly withdrawn.

## Current state

`apps/backend/app/repositories/dashboard_repository.py:41-45` — the omission:

```python
OUTSTANDING_CAPITAL_CALL_STATUSES = (
    CapitalCallStatus.scheduled,
    CapitalCallStatus.sent,
    CapitalCallStatus.partially_paid,
)
```

This tuple is consumed at two sites in the same file: the
`capital_calls_outstanding` count (~line 190) and the `upcoming_capital_calls`
list (~line 284). Both inherit the bug.

The cron that creates the invisible state is
`apps/backend/app/repositories/capital_call_repository.py:325-347`
(`mark_overdue`), registered in `app/worker.py` as
`cron_mark_overdue_capital_calls`.

`apps/backend/app/repositories/capital_call_repository.py:189-204` (`add_items`)
inserts items, calls `recompute_totals` per commitment, and commits — it never
calls `self.recompute_status(call_id)`. The only guard is the existence check at
lines 160-162. `apps/backend/app/repositories/distribution_repository.py:196-211`
has the identical shape.

Neither router gates on status:
`apps/backend/app/routers/capital_calls.py:158-213`
(`POST /capital-calls/{id}/items`) calls `repo.add_items` with no status check.

The status transition table to consult is
`apps/backend/app/repositories/capital_call_repository.py:22-50`
(`_ALLOWED_TRANSITIONS`), where `paid` maps to an empty set — i.e. `paid` is
declared terminal.

Test files to extend: `apps/backend/tests/test_dashboard.py` and
`apps/backend/tests/test_capital_calls_api.py`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Targeted | `cd apps/backend && uv run pytest tests/test_dashboard.py tests/test_capital_calls_api.py tests/test_distributions_api.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |

## Scope

**In scope**:
- `apps/backend/app/repositories/dashboard_repository.py`
- `apps/backend/app/repositories/capital_call_repository.py`
- `apps/backend/app/repositories/distribution_repository.py`
- `apps/backend/app/routers/capital_calls.py`
- `apps/backend/app/routers/distributions.py`
- `apps/backend/tests/test_dashboard.py`, `test_capital_calls_api.py`, `test_distributions_api.py`

**Out of scope** (do NOT touch):
- `recompute_status`'s zero-paid branch — a real, separate defect (a call cannot
  return to `sent` once a payment is unwound to zero). It needs a data-repair
  decision, so it is deliberately deferred. Do **not** fix it here.
- `mark_overdue` itself — its behavior is correct; the dashboard's definition is
  what is wrong.
- `_ALLOWED_TRANSITIONS` — read it, don't change it.
- The pro-rata allocation block in these routers — plan 007 owns it. Expect a
  conflict if you touch it.

## Git workflow

- Branch: `advisor/005-capital-call-status`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 0 (READ FIRST): the conflicting test — decision already made

A first execution attempt correctly STOPPED here, because step 1 breaks an
existing test that asserts the opposite. That conflict has now been
investigated and **the decision is: proceed with the fix and update the test.**

The test is `tests/test_dashboard.py::TestDashboardOverview::test_aggregates_filtered_to_user_organization`,
which seeds an `overdue` call with this comment (~lines 335-336):

```python
                    # `overdue` must NOT count toward outstanding (only scheduled,
                    # sent, and partially_paid do).
```

That comment describes the *implementation*, not a product decision, and the
assertion is tautological — it asserts the code does what the code does. The
evidence that the current behavior is wrong:

1. **There is no other overdue surface.** `app/schemas/dashboard.py:57` defines
   only `capital_calls_outstanding: int` — there is no separate overdue count,
   and `grep -n overdue app/repositories/dashboard_repository.py` returns
   **nothing**. Overdue calls are not bucketed elsewhere; they are counted
   nowhere at all.
2. **A cron actively moves calls into that invisible state.**
   `capital_call_repository.mark_overdue` runs daily and flips past-due
   `sent`/`partially_paid` calls to `overdue`. So a call is visible as
   outstanding, and then silently is not.
3. **Another module already disagrees.**
   `app/services/payment_matching.py:36-40` defines `_COLLECTIBLE_STATUSES` as
   `sent`, `partially_paid`, **and `overdue`**, commented "Only calls that are
   actually out for collection make sensible targets." The payment matcher
   treats overdue money as collectible while the dashboard treats it as gone.
4. In fund administration, "outstanding" means capital called but not yet
   received. Money that is *late* is the most outstanding money there is.

So: update the test to assert `overdue` **is** counted, and rewrite its comment
to say why (past-due calls must stay visible; they are the ones needing
collection). Note in your report that you changed a test's asserted behavior —
that is a deliberate behavior change, not a mechanical fix.

If you disagree after reading the code, STOP and say so rather than proceeding.

### Step 1: Include `overdue` in the outstanding statuses

Add `CapitalCallStatus.overdue` to `OUTSTANDING_CAPITAL_CALL_STATUSES` in
`apps/backend/app/repositories/dashboard_repository.py:41-45`.

Then check the ordering of the `upcoming_capital_calls` query — it orders by
`due_date` ascending, which now places past-due calls at the top. That is the
desired reading ("most urgent first"), but confirm the panel's label still makes
sense; if the query is explicitly named/filtered as *future* calls, report that
rather than silently changing its meaning.

**Verify**: `cd apps/backend && uv run pytest tests/test_dashboard.py -v` → all pass.

### Step 2: Test that an overdue call is counted

Add a test to `apps/backend/tests/test_dashboard.py`: seed a capital call with
status `overdue` and assert it appears in both `capital_calls_outstanding` and
the upcoming list. Model it on the existing dashboard tests in that file.

Confirm the test **fails** against the step-1-reverted code.

**Verify**: `cd apps/backend && uv run pytest tests/test_dashboard.py -v` → all pass, 1 new test.

### Step 3: Reject allocations on closed calls and recompute status

In `apps/backend/app/repositories/capital_call_repository.py`, in `add_items`:

- Before inserting, raise `ValueError` if the call's status is `paid` or
  `cancelled`. Use a message consistent with the file's existing `ValueError`
  style so the router's error mapping stays uniform.
- After the inserts and `recompute_totals` calls, and **before** the commit,
  call `self.recompute_status(call_id)`.

Apply the identical change to `add_items` in
`apps/backend/app/repositories/distribution_repository.py:196-211`, using that
file's own status enum and transition table.

In both routers (`capital_calls.py`, `distributions.py`), map the new
`ValueError` to a **409 Conflict** — the request is well-formed but conflicts
with the resource's state. Follow how those routers already translate
`ValueError` from the repository; if the existing convention is 400, match that
instead of introducing a second convention, and note which you chose.

**Verify**: `cd apps/backend && uv run pytest tests/test_capital_calls_api.py tests/test_distributions_api.py -v` → all pass.

### Step 4: Test the status gate

Add tests to `test_capital_calls_api.py` and `test_distributions_api.py`:

- Adding an item to a `paid` call is rejected with the chosen status code.
- Adding an item to a `cancelled` call is rejected.
- Adding an item to a `sent` call still succeeds **and** the call's status is
  recomputed afterwards (assert the status value, not just a 2xx).

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures, ~5 new tests.

## Test plan

- New tests listed in steps 2 and 4.
- The overdue-dashboard test and the paid-call-rejection test are the two that
  must fail against pre-fix code — verify both do.
- Model after existing tests in the same files.
- Verification: `cd apps/backend && uv run pytest -q` → all pass.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `grep -n 'overdue' apps/backend/app/repositories/dashboard_repository.py` shows it in the outstanding tuple
- [ ] `add_items` in both repositories calls `recompute_status` before committing
- [ ] Tests exist for: overdue counted on dashboard; add-item rejected on paid; add-item rejected on cancelled
- [ ] `recompute_status`'s zero-paid branch is **unchanged** (`git diff` shows no edit to it)
- [ ] `git diff --name-only` contains no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- (RESOLVED — see Step 0. The known conflicting test in `test_dashboard.py` is
  expected; update it per Step 0. STOP only if you find a *different* test, or
  an overdue surface elsewhere in the dashboard that this plan missed.)
- The `upcoming_capital_calls` query turns out to filter on a future `due_date`
  explicitly, making "upcoming" semantically exclude overdue.
- Rejecting adds on `paid` calls breaks an existing test — that would indicate a
  legitimate workflow (e.g. correcting an allocation after payment) this plan
  did not account for. Report it; do not weaken the gate.
- You find yourself needing to change `recompute_status` to make anything pass.

## Maintenance notes

- **Deliberately deferred, and worth scheduling**: `recompute_status` cannot
  unwind. When `total_paid` returns to 0 its `else` branch preserves the current
  status, so a call corrected to zero stays `partially_paid` forever — it can
  never return to `sent`/`overdue`, and `mark_overdue` will keep considering it.
  The same drift exists in `distribution_repository`. Fixing it needs a decision
  about repairing existing rows, which is why it is not bundled here.
- Also unaddressed: `recompute_status` writes `call.status` directly without
  consulting `_ALLOWED_TRANSITIONS`, so the "terminal `paid`" guarantee is not
  actually enforced — two code paths disagree about what a `paid` call may
  become. Worth a follow-up that routes both through one checked helper.
- A reviewer should scrutinize: that `recompute_status` is called *before* the
  commit in `add_items` (after it, the status write would land in a separate
  transaction), and that the router error mapping matches the file's existing
  convention rather than introducing a new one.
