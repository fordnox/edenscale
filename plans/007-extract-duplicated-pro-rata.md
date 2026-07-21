# Plan 007: Extract the duplicated pro-rata commitment query into the repository

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/routers/capital_calls.py apps/backend/app/routers/distributions.py apps/backend/app/repositories/commitment_repository.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: tech-debt
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

The query that selects which commitments receive a pro-rata allocation is
duplicated **verbatim** between the capital-calls router and the distributions
router. The two copies differ only in `call.fund_id` vs `distribution.fund_id`.

This matters more than ordinary duplication because **the ordering is
load-bearing**. `allocate_pro_rata` distributes the rounding remainder
positionally — the last commitments in the ordered list absorb the leftover
cents. So `order_by(Commitment.created_at, Commitment.id)` determines *which LP
pays the extra cent*. If someone fixes or changes the ordering in one file and
not the other, capital calls and distributions will round in opposite directions
on the same fund, and the resulting discrepancy will be extremely hard to trace
back to its cause.

Both copies also violate this repo's own stated architecture. `CLAUDE.md` says
business logic lives in repositories, not route handlers. These are the only
four raw `db.query(...)` calls in the entire `app/routers/` tree — everything
else goes through a repository — so this is drift from an otherwise
well-maintained convention, not the house style.

## Current state

`apps/backend/app/routers/capital_calls.py:173-192`:

```python
    fund = _load_fund(db, call.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    allocations: list[tuple[uuid.UUID, Decimal]]
    if mode == "pro-rata":
        approved = (
            db.query(Commitment)
            .filter(
                Commitment.fund_id == call.fund_id,
                Commitment.status == CommitmentStatus.approved,
            )
            .order_by(Commitment.created_at, Commitment.id)
            .all()
        )
        if not approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approved commitments on this fund to allocate",
            )
        try:
```

`apps/backend/app/routers/distributions.py:174-193` — identical apart from
`distribution.fund_id`:

```python
    fund = _load_fund(db, distribution.fund_id)  # type: ignore[invalid-argument-type]
    assert fund is not None
    _ensure_org_scope(membership, fund)
    allocations: list[tuple[uuid.UUID, Decimal]]
    if mode == "pro-rata":
        approved = (
            db.query(Commitment)
            .filter(
                Commitment.fund_id == distribution.fund_id,
                Commitment.status == CommitmentStatus.approved,
            )
            .order_by(Commitment.created_at, Commitment.id)
            .all()
        )
        if not approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approved commitments on this fund to allocate",
            )
        try:
```

The complete set of raw router queries (verify with
`grep -rn "db\.query(" apps/backend/app/routers/`):
- `capital_calls.py:179` ← this plan
- `distributions.py:180` ← this plan
- `communications.py:215`, `communications.py:269` ← **out of scope**

Repository conventions to follow: see `apps/backend/app/repositories/commitment_repository.py`
for constructor shape (`def __init__(self, db: Session)`) and method style. Per
`CLAUDE.md`: "After creating new repository, schema, model, service, task -
update app/*/__init__.py file with new imports."

Existing coverage that pins the allocation results (these must keep passing
unchanged — they are the safety net for this refactor):
- `apps/backend/tests/test_capital_calls_api.py` — pro-rata allocation cases
- `apps/backend/tests/test_distributions_api.py` — pro-rata allocation cases
- `apps/backend/tests/test_allocation_service.py` — `allocate_pro_rata` itself

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Targeted | `cd apps/backend && uv run pytest tests/test_capital_calls_api.py tests/test_distributions_api.py tests/test_allocation_service.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Import smoke test | `cd apps/backend && uv run python -c "from app import *"` | exit 0 |

## Scope

**In scope**:
- `apps/backend/app/repositories/commitment_repository.py`
- `apps/backend/app/repositories/__init__.py` (only if a new export is needed)
- `apps/backend/app/routers/capital_calls.py`
- `apps/backend/app/routers/distributions.py`

**Out of scope** (do NOT touch):
- `communications.py:215` and `:269` — also raw queries, also worth extracting,
  but unrelated to the rounding-divergence risk. Separate change.
- `app/services/allocation.py` — `allocate_pro_rata` is correct and tested.
  Do not modify it.
- The `mode != "pro-rata"` branches in either router.
- Any change to allocation **results**. This is a pure extraction: the same
  commitments in the same order must come back. If any test's expected split
  amounts change, you have broken it.

## Git workflow

- Branch: `advisor/007-extract-pro-rata-query`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the repository method

In `apps/backend/app/repositories/commitment_repository.py`, add:

```python
    def list_approved_for_allocation(self, fund_id: uuid.UUID) -> list[Commitment]:
        """Approved commitments on a fund, in allocation order.

        The ordering is load-bearing: ``allocate_pro_rata`` assigns the rounding
        remainder positionally, so this order decides which commitment absorbs
        the leftover cents. Capital calls and distributions must both use this
        method so they can never diverge.
        """
        return (
            self.db.query(Commitment)
            .filter(
                Commitment.fund_id == fund_id,
                Commitment.status == CommitmentStatus.approved,
            )
            .order_by(Commitment.created_at, Commitment.id)
            .all()
        )
```

Match the file's existing import style and constructor. Add the export to
`apps/backend/app/repositories/__init__.py` if that file enumerates symbols
rather than modules — check before editing.

**Verify**: `cd apps/backend && uv run python -c "from app import *"` → exit 0.

### Step 2: Use it from the capital-calls router

Replace the raw query at `capital_calls.py:179-186` with a call to
`CommitmentRepository(db).list_approved_for_allocation(call.fund_id)`.

Keep the `if not approved:` 400 exactly as it is — same status, same detail
string. Existing tests assert on that message.

Remove now-unused imports (`Commitment`, `CommitmentStatus`) **only if** nothing
else in the file uses them — check first; `ruff check` will also tell you.

**Verify**: `cd apps/backend && uv run pytest tests/test_capital_calls_api.py -v` → all pass.

### Step 3: Use it from the distributions router

Same change in `distributions.py:180-187`, passing `distribution.fund_id`.

**Verify**: `cd apps/backend && uv run pytest tests/test_distributions_api.py -v` → all pass.

### Step 4: Replace the `assert` guards with real 404s

Both routers use `assert fund is not None` (`capital_calls.py:174`,
`distributions.py:175`) as a runtime guard in request-handling code. Python run
with `-O` strips asserts, and an `AssertionError` surfaces as a 500 rather than
a meaningful status.

Replace each with an explicit `raise HTTPException(404, ...)`, matching how
these routers already raise 404 for a missing call/distribution a few lines
above.

Check whether the `# type: ignore[invalid-argument-type]` comment on the
preceding `_load_fund` line becomes unnecessary once the narrowing is explicit;
remove it if `ruff`/`ty` no longer need it, keep it if they do.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 5: Confirm the duplication is gone

**Verify**: `grep -rn "db\.query(" apps/backend/app/routers/` → returns exactly
two matches, both in `communications.py`.

## Test plan

- **No new tests required.** The existing pro-rata tests in
  `test_capital_calls_api.py` and `test_distributions_api.py` already pin the
  resulting split amounts, which is precisely what must not change.
- Optionally add one direct unit test for `list_approved_for_allocation`
  asserting it returns only `approved` commitments in `created_at, id` order —
  cheap, and it pins the ordering contract at the level where it now lives.
- Verification: `cd apps/backend && uv run pytest -q` → all pass, with **no
  changes to any expected allocation amount** in any test.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `cd apps/backend && uv run python -c "from app import *"` exits 0
- [ ] `grep -rn "db\.query(" apps/backend/app/routers/` returns exactly 2 matches, both in `communications.py`
- [ ] `grep -rn "assert fund is not None" apps/backend/app/routers/` returns no matches
- [ ] `git diff` shows **no change to any expected allocation amount** in any test file
- [ ] `git diff --name-only` contains no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The two excerpts are not in fact identical in the live code (i.e. they have
  already diverged) — that is a **more serious finding** than the duplication
  itself. Report the difference and stop; the divergence needs a decision about
  which behavior is correct before it is unified.
- Any test's expected allocation amount changes.
- Replacing an `assert` with a 404 breaks a test that expected a 500.
- `CommitmentRepository` turns out to already have an equivalent method — use it
  instead of adding a second, and say so in your report.

## Maintenance notes

- The docstring on the new method is the durable artifact here. The reason both
  call sites must share one implementation is non-obvious (positional remainder
  assignment) and easy to undo in a future refactor. Do not let it be trimmed.
- Follow-up worth doing separately: `communications.py:215,269` are the last two
  raw router queries; extracting them would make "no `db.query` in routers" an
  invariant that can be enforced by a grep in CI.
- A reviewer should scrutinize: that the ordering clause is byte-identical to
  what both routers used before, and that no expected split amount moved in any
  test.
