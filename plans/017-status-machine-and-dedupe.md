# Plan 017: Let payments unwind, enforce the transition table, and stop collapsing distinct payments

> **Executor instructions**: Follow step by step. Run every verification command.
> If a STOP condition occurs, stop and report — do not improvise.
>
> **Drift check**: `git diff --stat HEAD -- apps/backend/app/repositories/capital_call_repository.py apps/backend/app/repositories/distribution_repository.py apps/backend/app/services/iso20022.py`

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (changes status values on existing rows; changes dedupe semantics)
- **Depends on**: plans 003 and 005 (both merged)
- **Category**: bug
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21

## Why this matters

Three correctness defects deliberately deferred from earlier plans because each
needs a decision rather than a mechanical fix.

**(a) A payment cannot be unwound.** In `recompute_status`, when `total_paid`
drops back to 0 the `else` branch sets `new_status = call.status` — silently
preserving `partially_paid`. So correcting a mis-keyed payment to zero leaves
the call stuck at `partially_paid` **forever** with nothing paid. It can never
return to `sent`/`overdue`, and since plan 005 made `overdue` count toward
outstanding, the dashboard now mislabels it too.

**(b) The state machine is not actually enforced.** `recompute_status` writes
`call.status` directly, never consulting `_ALLOWED_TRANSITIONS`, where `paid`
maps to an empty set (i.e. terminal). A reduced payment therefore moves
`paid → partially_paid`, a transition `transition_status` would reject. Two code
paths disagree about what a `paid` call may become.

**(c) Two genuinely distinct payments can collapse into one.** When a bank
statement entry has no reference, `iso20022.py` composes a synthetic one from
`value_date|amount|payer`. Two real credits sharing those three values — an
investor paying two equal tranches, or two LPs behind one corporate payer name —
produce the same key. The second is then either dropped at import
(`create_import` skips references already `seen` in the same file) or
auto-`ignored` at apply time (`_reference_already_applied` treats it as already
settled). **That is money the fund received and never recorded.**

The comment at `bank_import_repository.py:37-39` asserts "a statement should
never list the same transaction twice" — true for real bank references, false
for this synthetic one.

## Current state

`apps/backend/app/repositories/capital_call_repository.py`:
- `_ALLOWED_TRANSITIONS` (~lines 22-50) — `paid` maps to an empty set.
- `recompute_status` (~lines 296-304) — writes `call.status` directly; the
  zero-paid `else` branch preserves the current status.
- `transition_status` — the method that *does* consult the table.

`apps/backend/app/repositories/distribution_repository.py` (~lines 318-325) —
identical logic, identical drift from its own `_ALLOWED_TRANSITIONS` (~22-43).

`apps/backend/app/services/iso20022.py` (~lines 171-172) — the synthetic
reference fallback.

`apps/backend/app/repositories/bank_import_repository.py`:
- `create_import` (~lines 51-56) — drops entries whose `bank_reference` was
  already `seen` within the same file.
- `_reference_already_applied` (~lines 129-143) — treats an equal reference in
  another import as already settled.

Note `apply()` was restructured by plan 003 into validate-then-write phases with
a single commit. Preserve that structure.

Tests that pin current behavior — read before changing:
`tests/test_bank_imports_api.py` (the dedupe test around line 315 is the one
step 3 affects), `tests/test_capital_calls_api.py`, `tests/test_distributions_api.py`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `cd apps/backend && uv run pytest -q` | all pass, 0 failed |
| Lint | `make lint` (repo root) | exit 0 |

Environment (both): `export APP_DOMAIN=localhost` and an isolated
`APP_DATABASE_DSN` (suffix `_wt017`). Never print the DSN.

## Scope

**In scope**:
- `apps/backend/app/repositories/capital_call_repository.py`
- `apps/backend/app/repositories/distribution_repository.py`
- `apps/backend/app/services/iso20022.py`
- `apps/backend/app/repositories/bank_import_repository.py` (dedupe paths only)
- corresponding test modules

**Out of scope**:
- `apply()`'s phase structure and single-commit behavior from plan 003 — do not
  restructure it.
- The `add_items` status gate from plan 005 — already correct.
- Any migration / data repair of existing rows (see STOP conditions).

## Steps

### Step 1: Let `recompute_status` unwind to the right status

In the zero-paid branch, instead of preserving the current status, derive the
correct one: `overdue` if the call is past due, else `sent` — but only when the
call had actually been sent. A `draft` or `scheduled` call that has no payments
must not be promoted to `sent`. Read the status enum and the surrounding logic
to get the full set of cases right; enumerate them in your report.

Apply the equivalent change in `distribution_repository`, using that module's
own statuses (distributions may not have an `overdue` concept — check).

**Verify**: `cd apps/backend && uv run pytest tests/test_capital_calls_api.py tests/test_distributions_api.py -v` → all pass.

### Step 2: Route status writes through a checked helper

Add a private helper used by `recompute_status` that asserts the target status
is reachable from the current one per `_ALLOWED_TRANSITIONS`, and use it instead
of assigning `call.status` directly.

`recompute_status` legitimately needs some transitions the table does not yet
permit (notably `paid → partially_paid` when a payment is reduced). **Widen the
table to allow them explicitly**, rather than bypassing the check — the point is
that every legal transition is declared in one place. Document each entry you
add with a brief comment saying why.

If widening the table would make `paid` non-terminal in a way that breaks
`transition_status`'s guarantees for the *user-facing* send/cancel flows, STOP
and report — that is a genuine design tension needing a decision.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 3: Stop synthetic references from colliding

In `iso20022.py`, include the entry's **ordinal position within the statement**
in the composed fallback reference, so two otherwise-identical entries in one
file get distinct keys.

In `bank_import_repository`, make synthetic references **not** participate in
cross-import `_reference_already_applied` auto-ignoring — a synthetic key is not
evidence the same payment already settled. Either mark them (a flag on the
transaction, or a recognisable prefix) and skip them in that check, or flag them
for manual review instead of auto-ignoring. State which you chose.

The existing cross-import dedupe test (~`test_bank_imports_api.py:315`) uses
**real** references and must keep passing unchanged — real references are still
trustworthy dedupe keys. If it breaks, you have changed the wrong path.

**Verify**: `cd apps/backend && uv run pytest tests/test_bank_imports_api.py -v` → all pass.

### Step 4: Tests

- A payment corrected to zero returns the call to `sent` (or `overdue` if past
  due), not stuck at `partially_paid`. **Must fail pre-fix** — verify and report.
- A `paid` call whose payment is reduced moves to `partially_paid` via the
  checked helper without raising.
- A `draft`/`scheduled` call with no payments is not promoted.
- Two statement entries with identical date+amount+payer and no bank reference
  both import as distinct transactions. **Must fail pre-fix** — verify and report.
- The existing real-reference cross-import dedupe still ignores the duplicate.

**Verify**: `cd apps/backend && uv run pytest -q` → all pass, 5+ new tests.

## Done criteria

- [ ] `cd apps/backend && uv run pytest -q` → 0 failures
- [ ] `make lint` → exit 0
- [ ] `recompute_status` no longer assigns `call.status` directly in either repository
- [ ] Every transition `recompute_status` performs is declared in `_ALLOWED_TRANSITIONS`
- [ ] A test proves a zero-corrected payment unwinds (fails pre-fix)
- [ ] A test proves two identical-looking unreferenced entries import distinctly (fails pre-fix)
- [ ] The real-reference dedupe test passes **unchanged**
- [ ] `git diff --name-only` contains no file outside the in-scope list

## STOP conditions

- Existing rows in a real database would need repairing to be consistent with
  the new status logic — report the shape of the problem; a data migration is a
  separate decision and is **not** in this plan.
- Widening `_ALLOWED_TRANSITIONS` would break the user-facing send/cancel
  guarantees enforced by `transition_status`.
- Step 3 breaks the real-reference cross-import dedupe test in a way you cannot
  resolve without weakening it — that test encodes a genuine anti-double-pay
  requirement.
- You find that changing the synthetic key format would orphan existing
  persisted `bank_reference` values in a way that matters (check whether any
  are stored long-term and compared later).

## Maintenance notes

- **Existing data is not repaired by this plan.** Any call already stuck at
  `partially_paid` with zero paid stays stuck until touched. Worth a one-off
  audit query after this lands.
- The synthetic-reference format is now positional, so re-importing the *same*
  file produces the same keys (good) but a re-exported statement with entries in
  a different order would not (acceptable — real references are the reliable
  path, and this only affects entries the bank failed to reference at all).
- Reviewer should scrutinize: the enumerated status cases in step 1, and that no
  transition bypasses the checked helper.
