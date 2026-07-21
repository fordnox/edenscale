# Plan 003: Make bank-statement apply atomic and surface its errors in the UI

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- apps/backend/app/repositories/bank_import_repository.py apps/backend/app/repositories/capital_call_repository.py packages/api/src/client.ts apps/manager/src/pages/ImportBankPaymentsPage.tsx`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-green-suite-and-ci.md
- **Category**: bug
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

**This plan fixes a bug that overstates how much money a fund has received.**

`BankStatementImportRepository.apply()` writes payments onto capital-call items
in a loop. Each iteration calls `set_item_payment`, which **commits**. The
transaction's own `status = applied` is set *after* that commit. So when
assignment *k+1* raises `ValueError` (invalid item, or an item outside the
organization), the router catches it and calls `db.rollback()` — but assignment
*k*'s `amount_paid` increment is **already committed**, while its
`txn.status = applied` is rolled back.

The result: the API returns 400, the wizard stays on the review screen, and the
transaction still reads `unmatched`. Re-submitting applies that same amount
**again** — the idempotency guard `_reference_already_applied` cannot catch it,
because it only matches transactions whose status is `applied`, and this one's
status was rolled back.

That inflates `amount_paid`, which propagates into `called_amount`, DPI, TVPI
and IRR. A fund manager sees the fund as having received money it did not.

The second half of this plan is what makes the first half dangerous in practice.
`ImportBankPaymentsPage.handleApply` has an **empty catch block** whose comment
asserts "The api client surfaces the error toast" — but the API client imports
`toast` from `sonner` and **never calls it**. So on the 400, the manager sees no
error at all: no toast, no inline message, the wizard just sits there. The
natural response is to press Apply again, which is precisely the action that
double-pays. The unused import is the evidence that this was intended and lost.

## Current state

`apps/backend/app/repositories/bank_import_repository.py:145-214` is the whole
function. The load-bearing section, lines 162-194:

```python
        for assignment in assignments:
            txn = by_id.get(assignment.transaction_id)
            if txn is None:
                raise ValueError(
                    f"Transaction {assignment.transaction_id} is not part of this import"
                )
            if txn.status == BankPaymentTransactionStatus.applied:
                continue  # idempotent re-apply
            if self._reference_already_applied(
                bank_reference=txn.bank_reference,
                organization_id=organization_id,
                exclude_txn_id=txn.id,
            ):
                txn.status = BankPaymentTransactionStatus.ignored
                continue
            item = self._item_in_org(
                assignment.capital_call_item_id,
                organization_id,
            )
            if item is None:
                raise ValueError(                      # <-- raises mid-loop,
                    f"Capital call item {assignment.capital_call_item_id} "
                    "not found in this organization"
                )
            new_amount_paid = Decimal(item.amount_paid) + assignment.amount
            paid_at = (
                datetime.combine(txn.value_date, time.min)
                if txn.value_date is not None
                else datetime.now()                    # <-- also BUG: local time, see step 4
            )
            self._capital_calls.set_item_payment(item.id, new_amount_paid, paid_at)
            txn.capital_call_item_id = item.id         # <-- after the commit inside ^
            txn.status = BankPaymentTransactionStatus.applied
```

`apps/backend/app/repositories/capital_call_repository.py:206-224` — the commit
that breaks atomicity is on the last-but-two line:

```python
    def set_item_payment(
        self,
        item_id: uuid.UUID,
        amount_paid: Decimal,
        paid_at: datetime | None = None,
    ) -> CapitalCallItem | None:
        item = (
            self.db.query(CapitalCallItem).filter(CapitalCallItem.id == item_id).first()
        )
        if item is None:
            return None
        item.amount_paid = amount_paid
        item.paid_at = paid_at
        self.db.flush()
        self._commitments.recompute_totals(item.commitment_id)
        self.recompute_status(item.capital_call_id)
        self.db.commit()        # <-- commits inside the caller's loop
        self.db.refresh(item)
        return item
```

**Callers of `set_item_payment`** (verified by grep — this is the complete list,
and it is why the change is safer than it looks):

- `apps/backend/app/repositories/bank_import_repository.py:192` (the loop above)
- `apps/backend/tests/test_commitments_api.py:507, 516, 562, 566`

It is **not** called from any router. So adding an opt-out parameter changes no
production call site other than the one being fixed.

`packages/api/src/client.ts:3` imports toast; grep confirms exactly one
occurrence of the string `toast` in the file — the import itself:

```typescript
import { toast } from "sonner"
```

And the error path, `packages/api/src/client.ts:65`, only logs:

```typescript
      console.error(message)
```

`apps/manager/src/pages/ImportBankPaymentsPage.tsx:224-227`:

```typescript
    } catch {
      // The api client surfaces the error toast; keep the wizard on review.
    }
```

Existing tests that pin current apply behavior — read these before changing
anything, they must keep passing:
- `apps/backend/tests/test_bank_imports_api.py:219` — happy path suggest + apply
- `apps/backend/tests/test_bank_imports_api.py:277` — clean re-apply is idempotent
- `apps/backend/tests/test_bank_imports_api.py:315` — cross-import reference dedupe

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures |
| Bank import tests | `cd apps/backend && uv run pytest tests/test_bank_imports_api.py -v` | all pass |
| Lint (read-only) | `cd apps/backend && uv run ruff check .` | exit 0 |
| Frontend typecheck | `pnpm turbo run typecheck` | exit 0 |

## Scope

**In scope**:
- `apps/backend/app/repositories/bank_import_repository.py`
- `apps/backend/app/repositories/capital_call_repository.py` (`set_item_payment` signature only)
- `apps/backend/tests/test_bank_imports_api.py` (add cases)
- `packages/api/src/client.ts`
- `apps/manager/src/pages/ImportBankPaymentsPage.tsx` (the catch block only)

**Out of scope** (do NOT touch):
- `apps/backend/app/repositories/distribution_repository.py` — it has a
  `set_item_payment` too, but distributions are not written by the bank-import
  path. Leave it alone.
- `recompute_status` internals — its zero-paid branch has a separate defect
  (a call cannot return to `sent` once payment is unwound). That is deliberately
  **not** fixed here; see plans/README.md deferred list.
- `_reference_already_applied` and the synthetic-reference derivation in
  `apps/backend/app/services/iso20022.py` — a separate finding, separate plan.
- The bank-import wizard's UI flow beyond the single catch block.

## Git workflow

- Branch: `advisor/003-atomic-bank-apply`
- Commit per step; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Give `set_item_payment` a commit opt-out

In `apps/backend/app/repositories/capital_call_repository.py`, add a
keyword-only parameter `commit: bool = True` to `set_item_payment`. When
`commit` is false, skip **both** `self.db.commit()` and `self.db.refresh(item)`
— refreshing outside a committed transaction is pointless and can expire the
object mid-loop. Keep `self.db.flush()` and both recompute calls unconditional,
since the caller needs their effects visible within the transaction.

The default of `True` preserves every existing caller's behavior.

**Verify**: `cd apps/backend && uv run pytest tests/test_commitments_api.py -v` → all pass (these are the 4 existing callers).

### Step 2: Validate every assignment before writing anything

Restructure `apply()` into two phases. **Phase 1 — resolve and validate, no
writes:** iterate the assignments and build a list of resolved work items
(`txn`, `item`, `new_amount_paid`, `paid_at`), raising `ValueError` for any
unknown transaction or out-of-org item exactly as today. Skip already-applied
transactions and reference-duplicates as today, but record the
`ignored`-status decisions in a list rather than mutating during phase 1.

**Phase 2 — write:** only once phase 1 has completed without raising, apply the
status mutations and call `set_item_payment(..., commit=False)` for each
resolved work item.

Keep the single `self.db.commit()` at the end of the function (line 212 today)
as the **only** commit in the whole call.

The error messages and the conditions that trigger them must not change — the
router's 400 mapping and existing tests depend on them.

**Verify**: `cd apps/backend && uv run pytest tests/test_bank_imports_api.py -v` → all pass, including the idempotency and dedupe tests at :277 and :315.

### Step 3: Add the regression test for the partial-failure path

In `apps/backend/tests/test_bank_imports_api.py`, add a test that reproduces the
bug. Structure it after the existing apply tests in that file:

1. Seed an import with **two** transactions.
2. Call apply with two assignments: the first valid, the second naming a
   capital-call item that does not exist in the organization.
3. Assert the response is 400.
4. **Assert the first item's `amount_paid` is unchanged from its pre-call
   value** — this is the assertion that fails before step 2 and passes after.
5. Re-submit the same (still-invalid) request and assert `amount_paid` is
   *still* unchanged — proving no accumulation across retries.

**Verify**: `cd apps/backend && uv run pytest tests/test_bank_imports_api.py -v` → all pass including the new test. Confirm the new test **fails** if you temporarily revert step 2; if it passes against the old code, it does not reproduce the bug and must be rewritten.

### Step 4: Stamp `paid_at` in UTC

While in `apply()`, change the fallback at line 190 from `datetime.now()` to
`datetime.now(timezone.utc).replace(tzinfo=None)`.

The repo convention is naive-UTC to match the timezone-less `DateTime` columns —
see `apps/backend/app/repositories/user_repository.py:180-183` for the
documented idiom. `datetime.now()` returns server-local time, which lands
payments on the wrong calendar day in the IRR cashflow series
(`app/services/metrics.py:104-111` uses `paid_at.date()`) and can put a
New-Year-boundary payment in the wrong year on the dashboard.

Add a brief comment pointing at the convention. Ensure `timezone` is imported.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures.

### Step 5: Make the API client actually raise the toast

In `packages/api/src/client.ts`, call `toast.error(message)` on the error path
at line 65, alongside the existing `console.error`.

**Do not** fire a toast for the two branches that already handle themselves and
return early: the 401 path, and the 403 "Not a member of this organization"
org-fallback redirect at lines 55-62. Both navigate away; a toast there would be
noise on an unmounting page. Place the `toast.error` call after those guards.

Also add a toast to the `onError` network-failure handler below it — a dropped
connection currently produces two `console.error` lines and nothing visible.

**Verify**: `pnpm turbo run typecheck` → exit 0. And `grep -c 'toast' packages/api/src/client.ts` → returns 3 or more (import + at least two call sites).

### Step 6: Handle the apply error explicitly in the wizard

In `apps/manager/src/pages/ImportBankPaymentsPage.tsx`, replace the empty catch
block at lines 224-227. Now that step 5 makes the client toast, the comment's
premise is true — but relying on a side effect in another package is what caused
this bug. Set a local error state and render it inline near the Apply button, so
the failure is visible on the screen the user is looking at, and keep the wizard
on the review step as the current comment intends.

Match the file's existing state and error-rendering idiom — look at how
`currency_mismatch` warnings are surfaced around line 401 and follow that shape.

**Verify**: `pnpm turbo run typecheck` → exit 0.

## Test plan

- New backend test: the partial-failure regression in step 3 (the critical one).
- Existing tests that must keep passing unchanged:
  `test_bank_imports_api.py:219`, `:277`, `:315`.
- Model new tests after the existing apply tests in the same file.
- No new frontend tests — there is no component-test infrastructure in this repo
  yet, and standing it up is out of scope here. Verify steps 5 and 6 by
  typecheck plus a manual click-through if a dev environment is available.
- Verification: `cd apps/backend && uv run pytest -q` → all pass, 1+ new test.

## Done criteria

ALL must hold:

- [ ] `cd apps/backend && uv run pytest -q` exits 0 with 0 failures
- [ ] `cd apps/backend && uv run ruff check .` exits 0
- [ ] `pnpm turbo run typecheck` exits 0
- [ ] `apply()` in `bank_import_repository.py` contains exactly **one**
      `self.db.commit()` — verify: `grep -c 'db.commit()' apps/backend/app/repositories/bank_import_repository.py` returns 1
- [ ] `grep -n 'datetime.now()' apps/backend/app/repositories/bank_import_repository.py` returns **no matches**
- [ ] A test exists asserting `amount_paid` is unchanged after a 400 from a partial-failure apply, and it fails against the pre-fix code
- [ ] `grep -c 'toast' packages/api/src/client.ts` returns ≥ 3
- [ ] `ImportBankPaymentsPage.tsx` has no empty `catch {}` block
- [ ] `git diff --name-only` contains no file outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts in "Current state" do not match the live code.
- The new regression test in step 3 **passes** against the unmodified
  repository — it then isn't reproducing the bug, and the diagnosis needs
  revisiting before you change production code.
- Removing the mid-loop commit breaks `test_bank_imports_api.py:277` or `:315`
  in a way you cannot resolve without changing what those tests assert. Those
  two encode real idempotency requirements — **do not weaken them to get
  green**; report instead.
- `set_item_payment` turns out to have a caller you cannot see from grep (e.g.
  via `getattr` or a dynamic dispatch).
- Making the toast fire causes duplicate toasts on the 401/403 paths.

## Maintenance notes

- **The deeper pattern**: repositories in this codebase commit internally, which
  makes them unsafe to compose. `apply()` is the first place that bit. Any
  future multi-write operation across repositories will hit the same problem.
  The `commit: bool = True` parameter is a targeted fix, not a resolution — the
  longer-term answer is a unit-of-work/transaction boundary owned by the router.
  Flag that if more of these appear.
- A reviewer should scrutinize: that phase 1 performs **no** mutations (an
  accidental `txn.status = ...` in phase 1 reintroduces the bug in a subtler
  form), and that the single remaining commit is genuinely the only one on the
  path — including inside `recompute_totals` and `recompute_status`, which the
  executor should check for their own commits.
- Deliberately deferred: `recompute_status` cannot unwind a payment to zero
  (a call stuck at `partially_paid` forever), and the synthetic bank-reference
  dedupe key can collapse two genuine same-day same-amount payments. Both are
  real and both are separate plans.
