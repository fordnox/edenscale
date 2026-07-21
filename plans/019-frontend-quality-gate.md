# Plan 019: Add a frontend linter, split the manager bundle, and lift the triplicated modules

> **Executor instructions**: Follow step by step. Run every verification command.
> If a STOP condition occurs, stop and report — do not improvise.
>
> **Drift check**: `git diff --stat HEAD -- apps/manager/src apps/investor/src apps/superadmin/src packages/ui packages/shared`

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: MED (no frontend test coverage to refactor against)
- **Depends on**: plan 012 (merged — typecheck must be green first)
- **Category**: dx | perf | tech-debt
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21

## Why this matters

**(a) There is no frontend linter at all.** All five frontend packages define
`"lint": "tsc --noEmit"` — byte-identical to their `typecheck` script. So
nothing across ~23K lines of React catches `react-hooks/exhaustive-deps`
violations, floating promises, or unused variables. `turbo.json` defines a
`lint` task; it just has nothing meaningful to run. Combined with there being
only two frontend test files in the whole workspace, code review is the *only*
gate on the frontend.

**(b) Every user downloads the entire manager app to see the login screen.**
`apps/manager/src/App.tsx` imports 27 page and layout modules eagerly — not one
`React.lazy` or `Suspense`. That pulls in `recharts` (via
`components/funds/FundOverview.tsx`), the 1000+ line `OrganizationSettingsPage`,
and the bank-import wizard, all on the critical path for users who may never
open them.

**(c) Six modules are duplicated across apps.** `ProtectedLayout.tsx` is
**triplicated** (identical in all three apps); `useCommandPalette.ts` and
`InvitationAcceptPage.tsx` are near-identical pairs; `CommandPalette.tsx`
differs by ~15 lines out of 200. The invitation flow is security-adjacent (token
handling, role on accept) and is exactly where two copies drifting apart is
expensive. The infrastructure to fix this already exists and is already used —
`packages/ui` exports `./invitations/*` and `./PageHero`, `packages/shared`
exports `ActiveOrganizationContext` and `useActiveOrganization`.

## Current state

Verify each of these before acting — they are leads, not facts:

- `apps/manager/package.json`, `apps/investor/package.json`,
  `apps/superadmin/package.json`, `packages/ui/package.json`,
  `packages/shared/package.json` — each has `"lint": "tsc --noEmit"`.
- No `.eslintrc*`, `eslint.config.*`, or `biome.json` anywhere outside
  `node_modules`.
- `apps/manager/src/App.tsx` (~150 LOC) — 27 eager imports, no `React.lazy`.
- `apps/manager/src/components/funds/FundOverview.tsx` imports `recharts`.
- `apps/manager/src/pages/OrganizationSettingsPage.tsx` — largest frontend file.
- `apps/manager/src/layouts/ProtectedLayout.tsx`,
  `apps/investor/src/layouts/ProtectedLayout.tsx`,
  `apps/superadmin/src/layouts/ProtectedLayout.tsx` — ~31 lines each.
- `apps/manager/src/hooks/useCommandPalette.ts` and
  `apps/investor/src/hooks/useCommandPalette.ts` — ~26 lines each.
- `apps/manager/src/pages/InvitationAcceptPage.tsx` and
  `apps/investor/src/pages/InvitationAcceptPage.tsx` — ~170 lines, ~32-line diff.
- `apps/manager/src/components/CommandPalette.tsx` (~211) and
  `apps/investor/src/components/CommandPalette.tsx` (~182).

Existing shared-package conventions: look at how `packages/ui` and
`packages/shared` declare exports in their `package.json` and how consumers
import them (`@edenscale/ui/...`). Match that exactly.

`packages/shared` has **no** `test` script, so `turbo run test` skips it.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Typecheck | `pnpm turbo run typecheck` | 7/7 successful |
| Frontend tests | `pnpm turbo run test` | all pass |
| Build (for bundle) | `cd apps/manager && pnpm run build` | exit 0 |
| Install | `pnpm install` | exit 0 |
| Backend unaffected | `cd apps/backend && uv run pytest -q` | 0 failures |

## Scope

**In scope**:
- A root ESLint flat config + per-package `lint` script changes
- `apps/manager/src/App.tsx` (lazy routes)
- `packages/ui/src/**` and/or `packages/shared/src/**` (lifted modules) + their `package.json` exports
- `apps/{manager,investor,superadmin}/src/**` — only the files being lifted or their import sites
- `package.json` files for the lint dependency

**Out of scope**:
- Any backend file.
- Rewriting page logic — this plan moves and splits code, it does not redesign it.
- Fixing every lint violation the new config surfaces (see step 2 — land as
  warnings first).
- Adding frontend test infrastructure (MSW, component tests) — separate work.

## Steps

### Step 1: Add ESLint with the two rules that actually catch bugs

Add a root flat config (`eslint.config.js`) with `@typescript-eslint` and
`eslint-plugin-react-hooks`. The two rules worth having here are
`react-hooks/exhaustive-deps` and `@typescript-eslint/no-floating-promises` —
the first catches stale-closure bugs, the second catches unawaited mutations.

Change each package's `"lint"` script to actually run ESLint, and keep
`"typecheck"` as `tsc --noEmit` so the two turbo tasks stop being aliases.

`no-floating-promises` requires type-aware linting (a `project` reference in the
parser options). If that makes the lint run unacceptably slow across five
packages, enable it for `apps/manager` only and say so.

**Verify**: `pnpm turbo run lint` runs ESLint (not `tsc`) in every package.

### Step 2: Land the violations as warnings, then report the count

Run the new lint. **Expect a nontrivial count across ~23K lines.**

Set the new rules to `warn`, not `error`, so the gate is landable today, and
report the violation count per rule. Do **not** attempt to fix them all in this
plan — that is a separate, much larger piece of work, and mass-editing hook
dependency arrays without test coverage is how you introduce bugs.

If any violation looks like a **real** bug (a genuinely stale closure, an
unawaited mutation that could lose data), report it separately — those are
findings, not lint noise.

**Verify**: `pnpm turbo run lint` exits 0 (warnings don't fail); the count is reported.

### Step 3: Measure the bundle before splitting it

Run `cd apps/manager && pnpm run build` and record the chunk sizes. If
`rollup-plugin-visualizer` is easy to add, use it; otherwise Vite's own build
output is enough.

**Do this before step 4** so the improvement is measured rather than assumed.
Report before-and-after numbers. If the main chunk turns out to be small enough
that splitting is not worth the `Suspense` complexity, say so and skip step 4 —
that is a legitimate outcome.

**Verify**: build succeeds; baseline chunk sizes recorded.

### Step 4: Route-level code splitting in the manager app

Convert the 27 route components in `App.tsx` to `React.lazy`, keeping layouts
eager, and wrap the route tree in a single `<Suspense>` using the app's existing
loading UI (find it — don't invent a new spinner).

Prioritise the two clearest wins: the `recharts`-importing `FundOverview` path
and `ImportBankPaymentsPage`.

The main hazard is a missing `Suspense` boundary producing a blank frame. Click
through every route after the change, or at minimum verify each lazy import
resolves.

**Verify**: build succeeds; main chunk is measurably smaller; `pnpm turbo run typecheck` → 7/7.

### Step 5: Lift the duplicated modules, easiest first

In this order — each is independently verifiable, so commit-per-module:

1. **`ProtectedLayout`** — identical in all three apps, zero parameters. Move to
   `packages/ui`, re-export, delete the three copies.
2. **`useCommandPalette`** — near-identical pair, zero parameters. Same treatment.
3. **`InvitationAcceptPage`** — takes a `routes` prop to parameterise the
   `managerRoutes`/`investorRoutes` difference.
4. **`CommandPalette`** — takes an injected sources array plus the org-context
   hook.

Stop after any step that turns out to need more than a prop or two — report
rather than forcing an abstraction. A wrong shared abstraction is worse than
duplication.

**Verify** after each: `pnpm turbo run typecheck` → 7/7, `pnpm turbo run test` → pass.

## Done criteria

- [ ] `pnpm turbo run lint` runs ESLint in every frontend package and exits 0
- [ ] `pnpm turbo run typecheck` → 7/7
- [ ] `pnpm turbo run test` → all pass
- [ ] `cd apps/backend && uv run pytest -q` → 0 failures (nothing backend changed)
- [ ] Violation counts per rule reported
- [ ] Bundle sizes reported before and after step 4 (or a documented decision to skip)
- [ ] `ProtectedLayout` exists in exactly one place
- [ ] `grep -rn "tsc --noEmit" apps/*/package.json packages/*/package.json` shows it only under `typecheck`
- [ ] `git diff --name-only` contains no backend file

## STOP conditions

- ESLint surfaces a violation you believe is a **real bug** — report it as a
  finding; do not silently fix it inside a tooling change.
- Type-aware linting makes the lint run unusably slow even scoped to one app.
- A lifted module needs more than two props to serve both apps — the
  abstraction is wrong; report and leave the duplication.
- Route splitting produces a blank frame on any route you cannot resolve within
  one attempt.
- The measured bundle shows splitting would not meaningfully help.

## Maintenance notes

- The warn-not-error choice in step 2 is deliberate: it makes the gate
  installable today. Ratcheting individual rules to `error` as violations are
  burned down is the follow-up, and it should be done rule-by-rule.
- `packages/shared` still has no `test` script, so `turbo run test` skips it
  entirely — worth adding alongside tests for `format.ts`, which is the single
  rendering path for every money figure in all three apps.
- Reviewer should scrutinize: that no lifted module changed behavior (these are
  moves, and there is no frontend test coverage to catch a regression), and that
  every lazy route has a `Suspense` ancestor.
