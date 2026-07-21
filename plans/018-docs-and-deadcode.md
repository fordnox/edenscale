# Plan 018: Finish the docs reconciliation and remove dead configuration

> **Executor instructions**: Follow step by step. Run every verification command.
> If a STOP condition occurs, stop and report — do not improvise.
>
> **Drift check**: `git diff --stat HEAD -- docs/architecture apps/backend/app/models/user.py package.json pnpm-workspace.yaml`

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: LOW (one migration; otherwise docs and config)
- **Depends on**: plans 010 and 012 (both merged)
- **Category**: docs | tech-debt
- **Planned at**: branch `advisor/audit-improvements`, 2026-07-21

## Why this matters

Plan 010 corrected the two ADRs, the investor-portal plan, `CLAUDE.md`, and the
README — but it was scoped to those, and it **reported** that four more
architecture documents carry the same drift. Plan 012 fixed the duplicate
`@types/react` but **reported** that the mechanism meant to prevent it is dead
configuration. Both were correctly left for a follow-up. This is it.

Concretely:
- Four `docs/architecture/*.md` files still describe `users.role`,
  `users.organization_id`, `require_roles(*allowed)`, `PATCH /users/{id}/role`,
  and `WHERE organization_id = :user.organization_id` scoping as current. **All
  are false.** This repo is worked on by agents that read these files to orient.
- The root `package.json`'s `pnpm.overrides` block **has never applied**: pnpm
  11 prints `The "pnpm" field in package.json is no longer read by pnpm... "pnpm.overrides"`
  on every command. Overrides moved to `pnpm-workspace.yaml`, which has no
  `overrides` section. So nothing currently prevents a recurrence of the
  version-skew bug plan 012 just fixed.
- `users.password_hash` is dead: `apps/backend/app/models/user.py:26` is its
  only reference anywhere in the codebase. Auth is entirely Hanko.
- ADR-002 claims proxy uploads were rejected, but that is what shipped.

## Current state

**Stale architecture docs** (line numbers from the plan-010 report — verify
before editing, they are leads not facts):
- `docs/architecture/rbac-model.md` — lines 18, 24-28, 36, 41, 44, 47, 51, 55,
  61, 63, 103, 108, 112
- `docs/architecture/api-layering.md` — 27, 53, 63, 106-111, 128
- `docs/architecture/system-overview.md` — 68-69, 71
- `docs/architecture/database-schema.md` — 66, 118, 121

Ground truth to describe instead — verify each against the code:
- `apps/backend/app/models/user.py` has **no** `role` and **no**
  `organization_id`; it has `memberships` and an `is_superadmin` property
  derived from `settings.superadmin_emails`.
- `apps/backend/app/models/user_organization_membership.py` holds per-org roles.
- `apps/backend/app/core/rbac.py` exposes `get_active_membership`,
  `require_membership_roles`, `require_tenant_user`, `require_superadmin` —
  **not** `require_roles`. Active org travels on the `X-Organization-Id` header.
- `apps/backend/app/repositories/lp_scope.py` scopes LP visibility.
- `docs/decisions/adr-003-per-org-membership-roles.md` (created by plan 010) is
  the authoritative narrative — point at it rather than re-deriving.

`AGENTS.md` is vaguer and has no clearly false specific claim, but links to the
stale `rbac-model.md`.

**Dead pnpm overrides** — root `package.json`:
```json
    "overrides": {
      "@types/react": "19.2.17",
      "@types/react-dom": "19.2.3"
    }
```
inside a `"pnpm": { ... }` field that pnpm 11.15.1 ignores.
`pnpm-workspace.yaml` currently has `packages:` and `allowBuilds:` only.

**Dead column** — `apps/backend/app/models/user.py:26`:
```python
    password_hash = Column(String(255), nullable=False, default="")
```

**ADR-002's contradiction** — its "Why we did not pick Option B" rejects proxy
uploads as a bandwidth/latency tax that ties up an API worker, but
`S3Storage.presign_put` (`app/services/storage.py` ~185-200) returns an
API-relative `/documents/upload/{key}` and that route writes to the bucket
server-side. Uploads **are** proxied. Only `presign_get` is direct-to-bucket.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `cd apps/backend && uv run pytest -q` | all pass, 0 failed |
| Lint | `make lint` (repo root) | exit 0 |
| Migration | `make migration`, `make upgrade`, `make downgrade` | exit 0 |
| Install | `pnpm install` | exit 0 |
| Typecheck | `pnpm turbo run typecheck` | 7/7 |
| Override check | `pnpm install 2>&1 \| grep -i "no longer read"` | no match after step 2 |

Environment (both): `export APP_DOMAIN=localhost` and an isolated
`APP_DATABASE_DSN` (suffix `_wt018`). Never print the DSN.

## Scope

**In scope**:
- `docs/architecture/rbac-model.md`, `api-layering.md`, `system-overview.md`, `database-schema.md`
- `docs/decisions/adr-002-storage-port-pattern.md` (the Option B correction only)
- `package.json` (remove the dead `pnpm.overrides`), `pnpm-workspace.yaml` (add real `overrides`), `pnpm-lock.yaml` (regenerated)
- `apps/backend/app/models/user.py` (drop `password_hash`) + a generated migration

**Out of scope**:
- `docs/decisions/adr-001` and `adr-003` — plan 010 handled them correctly.
- `docs/Auto Run Docs/` — historical logs, they *should* describe the past.
- `AGENTS.md` — no false specific claim; leave it.
- Any dependency version bump (separate plan).
- Any application logic.

## Steps

### Step 1: Correct the four architecture docs

For each file, verify every RBAC claim against the code before rewriting it. Do
not copy this plan's line numbers blindly — open the files.

Describe the membership model as it actually is, and cross-reference
`docs/decisions/adr-003-per-org-membership-roles.md` rather than duplicating its
reasoning. Where a doc describes a *sequence* (request → auth → scoping), make
sure the `X-Organization-Id` header step appears — its absence is what would
lead someone to hand-roll an unscoped query.

If you cannot verify a claim from the code, mark it as an open question rather
than inventing an answer. A confidently wrong architecture doc is worse than a
missing one.

**Verify**: `grep -rn "require_roles\|users\.role\|user\.organization_id" docs/architecture/` → no matches presenting them as current.

### Step 2: Move the pnpm overrides where pnpm reads them

Add to `pnpm-workspace.yaml`:
```yaml
overrides:
  "@types/react": "19.2.17"
  "@types/react-dom": "19.2.3"
```
and delete the now-inert `"pnpm": { "overrides": ... }` block from the root
`package.json`.

Run `pnpm install`. Confirm the warning is gone and that exactly **one**
`@types/react` remains.

This is what stops the plan-012 bug recurring: right now the specifier alignment
in `apps/emails` is the only thing holding the workspace to one version.

**Verify**:
- `pnpm install 2>&1 | grep -i "no longer read"` → no match
- `ls -d node_modules/.pnpm/@types+react@*` → exactly one directory
- `pnpm turbo run typecheck` → 7/7

### Step 3: Drop the dead `password_hash` column

Confirm it is genuinely unreferenced first:
`grep -rn "password_hash" apps/backend --include="*.py" | grep -v alembic`
→ should show only the model line.

Remove the column from the model, generate a migration with `make migration`,
inspect the generated file, and exercise it **both ways** (`make upgrade`,
`make downgrade`, `make upgrade`).

A dropped column is not reversible for data. The downgrade will recreate the
column empty — that is fine here because the column has never held data (auth is
Hanko), but **say so explicitly in the migration's docstring** so a future
reader does not assume data was preserved.

**Verify**: `cd apps/backend && uv run pytest -q` → 0 failures; migration up and down both exit 0.

### Step 4: Correct ADR-002's upload-proxy claim

Add a dated correction note to ADR-002 recording that the shipped
`S3Storage.presign_put` returns an API-relative upload URL and the proxy writes
server-side — i.e. uploads **are** proxied, the tradeoff the ADR's "Option B"
section says was rejected. Only downloads are direct-to-bucket.

Do **not** rewrite the historical Option A/B/C analysis — append a correction,
matching how plan 010 handled ADR-001/002. Note that no evidence in code or git
history explains the divergence, and that this makes the upload-size buffering
concern (deferred finding) land on the API process, which is what the ADR was
trying to avoid.

**Verify**: `grep -n "proxied\|correction" docs/decisions/adr-002-storage-port-pattern.md` → the note is present.

## Done criteria

- [ ] `cd apps/backend && uv run pytest -q` → 0 failures
- [ ] `make lint` → exit 0
- [ ] `pnpm turbo run typecheck` → 7/7
- [ ] `pnpm install` emits no "no longer read by pnpm" warning
- [ ] `ls -d node_modules/.pnpm/@types+react@*` → exactly one
- [ ] `grep -rn "password_hash" apps/backend --include="*.py" | grep -v alembic` → no matches
- [ ] Migration exercised up **and** down
- [ ] `grep -rn "require_roles" docs/architecture/` → no matches as current behavior
- [ ] `git diff --name-only` contains no file outside the in-scope list

## STOP conditions

- `password_hash` turns out to be referenced somewhere the grep missed (a raw
  SQL string, a seed script, a fixture) — report rather than dropping it.
- Moving the overrides changes more than the `@types/react*` graph in the
  lockfile — a large lockfile diff means something else resolved differently.
- An architecture doc makes a claim you can neither confirm nor refute from the
  code — mark it open, do not guess.
- The `password_hash` migration cannot be downgraded cleanly.

## Maintenance notes

- These four docs drifted because nothing ties them to the code. The durable fix
  is a `CLAUDE.md` rule: when a change invalidates a decision or architecture
  doc, update it in the same PR. Worth proposing separately.
- After step 2, adding a dependency override requires editing
  `pnpm-workspace.yaml`, not `package.json`. Note it where contributors will see
  it.
- Reviewer should scrutinize: that the rewritten RBAC docs describe the
  `X-Organization-Id` scoping step, since omitting it is the specific mistake
  that leads to unscoped cross-tenant queries.
