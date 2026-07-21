# Plan 010: Correct the four documents that describe a system that no longer exists

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 77985cfe..HEAD -- docs/ CLAUDE.md README.md`

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW (documentation only — no code changes)
- **Depends on**: none (but see note about plans 002/004 below)
- **Category**: docs
- **Planned at**: commit `77985cfe`, 2026-07-21

## Why this matters

Four documents make confident claims about this codebase that are false. This
repo is worked on by AI agents (it ships a `CLAUDE.md` and an `AGENTS.md`), and
these are the files an agent reads *first* to orient itself. Wrong orientation
documents are worse than missing ones: they cause confidently wrong work.

Concretely, an agent reading these today would look for a `users.role` column
that does not exist, write a tenant filter that cannot compile, believe the
product has no NAV model when it has one, and target the wrong major versions of
React and React Router.

## Current state — the four drifts, all verified

**(1) ADR-001 describes an abandoned RBAC model.**
`docs/decisions/adr-001-rbac-via-hanko-jwt.md` is marked **Accepted** and says
users store `role` and `organization_id` locally (line ~37), default
`role = lp` (~46), a `PATCH /users/{id}/role` route (~61), repository scopes
filtering `WHERE organization_id = :user.organization_id` (~64), and a
`require_roles(*allowed)` gate (~85). Line ~92 lists multi-org membership as a
*hypothetical future* that "would require a `user_organizations` table and
reworking every repository scope."

That future already shipped. `apps/backend/app/models/user.py` has **no** `role`
column and **no** `organization_id` column. Roles live on
`apps/backend/app/models/user_organization_membership.py`. Superadmin is derived,
not stored — `apps/backend/app/models/user.py:64-70`:

```python
    @property
    def is_superadmin(self) -> bool:
        """Superadmins are defined by ``SUPERADMIN_EMAIL`` in config, never
        stored: a user is a superadmin iff their (Hanko-verified) email is
        listed there. Per-organization roles live on memberships."""
        return (self.email or "").lower() in settings.superadmin_emails
```

`app/core/rbac.py` still exists, but its gates are now
`get_active_membership` / `require_membership_roles` / `require_tenant_user` /
`require_superadmin` — **not** `require_roles`. Scoping is keyed on an
`X-Organization-Id` header (see the module docstring at `app/core/rbac.py:15-22`).

**(2) ADR-002 says S3 doesn't exist yet.**
`docs/decisions/adr-002-storage-port-pattern.md:49` says `STORAGE_BACKEND` is
"currently only `local`" and line ~51 calls `S3Storage` a **future**
implementation. But `S3Storage` is shipped (`apps/backend/app/services/storage.py`,
~line 185 onward), `apps/backend/app/core/config.py:50-56` defines the seven
`S3_*` settings, `apps/backend/tests/test_storage_s3.py` exercises it, and
`config/deploy.yml` deploys with it. The ADR also gives the dev-storage path as
`backend/dev_storage/<key>` while the code uses `APP_DATA_PATH/dev_storage`
(`storage.py:86`).

**(3) `docs/investor-portal-plan.md` is wrong about its own central premise.**
It states NAV / Fair Value / TVPI / RVPI are "**MISSING** — no valuation model
(deliberate)", that "TVPI was removed", and builds a phased roadmap around
"the central dependency" of building a valuation model first. But
`apps/backend/app/models/fund_valuation.py` exists — its own docstring says it
"Enables residual-value metrics (NAV, TVPI, RVPI) and the LP capital account at
fair value" — and `apps/backend/app/services/metrics.py:36-40,136-155` computes
`nav`, `dpi`, `tvpi`, `rvpi` today, with a batched `latest_fund_navs` at ~line
262. The document's strategic fork has already been resolved in the code.

**(4) `CLAUDE.md` states the wrong frontend major versions.**
It says React 18, Vite 7, and React Router v6. The manifests say **React 19.2,
Vite 8.1, React Router 7.18, TypeScript 6**. Verify with:
`grep -n '"react"\|"vite"\|"react-router-dom"\|"typescript"' apps/manager/package.json`.

Also: `README.md` is still titled `# Template` with the description
"Opinionated web project template for building projects with AI." It documents
only the backend stack, mentions none of the three React apps, and contains
**no setup steps at all** — no `make sync`, no `.env` copy, no `make db-init`,
no mention of the required Postgres or Redis.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Verify versions | `grep -n '"react"\|"vite"\|"react-router-dom"\|"typescript"' apps/manager/package.json` | actual versions |
| Verify no role column | `grep -n 'role' apps/backend/app/models/user.py` | no `Column` for role |
| List make targets | `make help` | the real command list |
| Backend tests | `cd apps/backend && uv run pytest -q` | 0 failures (must be unaffected) |

## Scope

**In scope**:
- `docs/decisions/adr-001-rbac-via-hanko-jwt.md` (status line only)
- `docs/decisions/adr-003-per-org-membership-roles.md` (create)
- `docs/decisions/adr-002-storage-port-pattern.md`
- `docs/investor-portal-plan.md`
- `CLAUDE.md` (the stack-version lines)
- `README.md`

**Out of scope** (do NOT touch):
- **Any file under `apps/` or `packages/`.** This plan changes zero lines of
  code. If a doc claim seems wrong, the doc is wrong — fix the doc.
- `docs/Auto Run Docs/` — historical build logs; they are *supposed* to describe
  the past.
- `docs/architecture/*.md` — not audited in detail for this plan. If you notice
  drift there, **report it**, don't fix it (unscoped edits to five more files
  would make this diff unreviewable).
- `AGENTS.md` — not audited for this plan; report drift rather than editing.

## Git workflow

- Branch: `advisor/010-refresh-docs`
- Commit per document; plain imperative messages.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Supersede ADR-001 rather than rewriting it

**Do not edit ADR-001's body.** An ADR is a historical record of a decision that
was genuinely made; rewriting it destroys the record. Change **only** its
`**Status:**` line to `Superseded by ADR-003` with the date.

Then create `docs/decisions/adr-003-per-org-membership-roles.md`, following the
exact frontmatter and section structure of ADR-001 and ADR-002 (type, title,
created, tags, related; then Context / Options considered / Decision /
Consequences / Implementation pointers / Revisit when).

It must record:
- **Context**: why single-role users stopped working — a user needing
  membership in more than one organization, which ADR-001 explicitly flagged as
  the trigger to revisit.
- **Decision**: roles live on `user_organization_membership` rows; the active
  organization travels on the `X-Organization-Id` header; superadmin is
  config-defined via `SUPERADMIN_EMAIL`, matched case-insensitively against the
  Hanko-verified email, and is **never** stored in the database.
- **Consequences**: state the security property explicitly — because superadmin
  is not a database column, a compromised admin-level database write cannot
  escalate to superadmin. That is a real benefit worth recording.
- **Implementation pointers**: `app/core/rbac.py` (`get_active_membership`,
  `require_membership_roles`, `require_tenant_user`, `require_superadmin`),
  `app/models/user_organization_membership.py`, `app/repositories/lp_scope.py`.

Read the actual code before writing each claim. Do not copy assertions from this
plan without verifying them.

**Verify**: `grep -n 'Superseded' docs/decisions/adr-001-rbac-via-hanko-jwt.md` → shows the new status; the new file exists with matching frontmatter.

### Step 2: Update ADR-002

Edit the Consequences section to record that `S3Storage` **has shipped** and is
what production deploys use. Correct the dev-storage path to
`APP_DATA_PATH/dev_storage`. Move the "implement S3Storage" item out of
"Revisit when" — it is done.

Add one explicit sentence to the accepted-tradeoffs section: dev-storage's
accepted unauthenticated exposure covers **uploaded blobs only**, never reads
outside the storage root.

**Note**: if plan 002 has landed, also record that `STORAGE_BACKEND` now fails
closed in a production-shaped configuration. Check whether that change is
present in your worktree (`grep -n 'model_validator' apps/backend/app/core/config.py`)
and describe reality — do not describe plan 002's intent if it has not landed.

**Verify**: `grep -n 'currently only' docs/decisions/adr-002-storage-port-pattern.md` → no match.

### Step 3: Correct the investor-portal plan

Update `docs/investor-portal-plan.md`:
- The gap table rows for NAV / Fair Value, TVPI, RVPI change from **MISSING** to
  done, citing `app/models/fund_valuation.py` and `app/services/metrics.py`.
- The "central dependency" section must record that the valuation model **has
  been built**, so the phases downstream of it are unblocked.
- Remove or correct the claim that "TVPI was removed".
- Re-check every other row in that table against the code before trusting it —
  if the doc was wrong about its central premise, other rows may be stale too.
  Report anything you cannot verify rather than guessing.

Add a dated note at the top recording when the document was last reconciled
against the code.

**Verify**: `grep -n 'deliberate)' docs/investor-portal-plan.md` → the "no valuation model (deliberate)" claim is gone.

### Step 4: Fix the stack versions in CLAUDE.md

Correct React 18 → 19.x, Vite 7 → 8.x, React Router v6 → v7, and add TypeScript
6. Use the **actual** values from the manifests, not this plan's numbers — check
`apps/manager/package.json` and the root `package.json`.

Consider writing major versions only (e.g. "React 19") rather than exact patch
versions, so the file does not go stale on every dependency bump.

Change nothing else in `CLAUDE.md`. Its architecture and coding-rules sections
were checked and are accurate.

**Verify**: `grep -n 'React 18\|Vite 7\|React Router v6' CLAUDE.md` → no matches.

### Step 5: Rewrite the README

Replace `README.md` with a real front page:

- What EdenScale **is**: a fund-administration platform for private-equity fund
  managers and their limited partners.
- The topology: one FastAPI backend serving three React SPAs (manager,
  investor, superadmin) plus an Astro marketing site and docs site, assembled by
  a Cloudflare Worker gateway.
- Prerequisites: Python 3.12, uv, Node + pnpm, Postgres, Redis.
- **Setup steps that actually work**, in order, using the real Makefile targets.
  Run `make help` and use what is there — `make sync`, copying `.env.example`,
  `make db-init` or `make upgrade`, `make db-seed`, then `make start-backend`,
  `make start-manager`, `make start-worker`.
- Keep the existing pre-commit rules section (`make test`, `make lint`,
  `make openapi`) — it is accurate in intent. **But** if plan 011 has landed and
  split `make lint` into checking and formatting targets, describe the new
  targets instead.
- Keep the competitor list, under a proper `##` heading (it is currently under a
  stray top-level `#`).

Do **not** invent commands. Every command in the README must exist in the
`Makefile` or a `package.json` script — verify each one before writing it down.

**Verify**: every command in the new README appears in `make help` output or in a `package.json` `scripts` block.

## Test plan

No tests — documentation only. The verification is that each claim is checkable
against the code, and each command is runnable.

Regression check: `cd apps/backend && uv run pytest -q` → 0 failures (proving
you changed no code).

## Done criteria

ALL must hold:

- [ ] `git diff --name-only` contains **no** file under `apps/` or `packages/`
- [ ] `cd apps/backend && uv run pytest -q` exits 0 (unchanged)
- [ ] ADR-001's status line says superseded; its body is otherwise unmodified
- [ ] `docs/decisions/adr-003-per-org-membership-roles.md` exists with frontmatter matching the other ADRs
- [ ] `grep -rn 'require_roles' docs/decisions/adr-003-*.md` → no match (the new ADR must not repeat the obsolete gate name)
- [ ] `grep -n 'currently only' docs/decisions/adr-002-storage-port-pattern.md` → no match
- [ ] `grep -n 'React 18\|Vite 7\|React Router v6' CLAUDE.md` → no match
- [ ] `README.md` no longer begins with `# Template` and contains working setup steps
- [ ] Every command in README.md exists in `make help` or a `package.json` script
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code contradicts this plan's description of the drift (e.g. `users.role`
  actually exists) — the plan is then stale and the docs may be right.
- Writing ADR-003 requires you to assert *why* a decision was made and you can
  find no evidence in the code or git history. Write what the code does; mark
  unknown rationale as an open question rather than inventing a justification.
  **A confidently wrong ADR is the exact failure mode this plan exists to fix.**
- A `make` target referenced in the README does not exist or fails.
- You find further drift in `docs/architecture/*.md` — report it, do not fix it.

## Maintenance notes

- ADR-001 → ADR-003 is the pattern to keep: supersede, never rewrite. The
  history of *why* the single-role model was chosen is genuinely useful context
  for anyone who later proposes going back to it.
- These four documents drifted because nothing ties them to the code. The
  cheapest durable fix is a line in `CLAUDE.md`'s coding rules: when a change
  invalidates a decision doc, supersede it in the same PR. Consider proposing
  that separately.
- A reviewer should scrutinize ADR-003 hardest — a new decision document that
  misstates the security model would be worse than the stale one it replaces.
  Every claim in it should be checkable against a named file.
