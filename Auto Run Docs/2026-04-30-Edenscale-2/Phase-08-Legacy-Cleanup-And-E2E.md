# Phase 08: Legacy Cleanup + End-to-End Verification

This final phase removes the deprecated `users.organization_id` column, deletes any remaining shims, and runs a full end-to-end verification of the multi-org world. It's intentionally last so the column stays around as a safety net while phases 02–07 proved out the new path. After this phase, the only place organization scoping lives is the `user_organization_memberships` table and the active membership context.

## Tasks

- [ ] Verify no read paths still reference `users.organization_id`:
  - Grep `backend/app/` for `organization_id` constrained to `User`/`user.organization_id`/`current_user.organization_id` references
  - Grep `frontend/src/` for `me.organization_id` and `user.organization_id`
  - Anything that still references the legacy column gets migrated to `activeMembership.organization_id` (frontend) or `active_membership.organization_id` (backend); document any references that legitimately need to stay (e.g. the alembic backfill migration itself) in `Auto Run Docs/2026-04-30-Edenscale-2/Working/legacy-org-id-references.md`

- [ ] Update the `User` model and schema:
  - Remove the `organization_id` column from `backend/app/models/user.py` and the `organization` relationship (keep the `memberships` relationship — that's the new world)
  - Remove `organization_id` from `UserRead`, `UserCreate`, `UserUpdate`, `UserSelfUpdate` in `backend/app/schemas/user.py`
  - Adjust `Organization.users` back-ref: replace it with `Organization.memberships` everywhere (already added in Phase 01)

- [ ] Update `get_current_user_record` in `backend/app/core/rbac.py`:
  - Remove the legacy "if email matches a seeded user, bind subject" path's reliance on the org column — the seed script (and the demo seed referenced in recent commits) needs updating to seed memberships instead. Read `backend/app/scripts/` (or wherever the demo seed lives — search the codebase) and update it accordingly
  - The default role for auto-provisioned users is now `UserRole.lp` (unchanged) but with NO membership — they appear in the "no organization yet" empty state from Phase 05 until they're invited
  - Make sure `get_current_user_record` still seed-claims correctly for the demo user (read the recent commit `293c56d` — "fix dev storage path + Hanko seed-claim flow" — to understand what behavior is required)

- [ ] Drop the column via alembic:
  - `cd backend && uv run alembic revision -m "drop legacy users.organization_id" --autogenerate`
  - The `upgrade()` should `op.drop_index` (if any) then `op.drop_column("users", "organization_id")`
  - The `downgrade()` adds the column back nullable and re-runs the seed-from-memberships logic (best-effort — fine if the downgrade is lossy, but document with a comment)
  - Run `make upgrade` against local SQLite; confirm passing

- [ ] Update the demo seed script:
  - Grep for the seed script the recent commits mention (`make seed` per commit `3b7139b`); update it to:
    1. Seed orgs as before
    2. Seed users WITHOUT an `organization_id`
    3. Seed `user_organization_memberships` rows with the appropriate per-org role
    4. Seed at least one superadmin user
  - Re-run `make seed` against a fresh local DB and verify the dashboard works end-to-end as the seeded admin

- [ ] Audit the OpenAPI surface for stale fields:
  - Run `make openapi`
  - Open `backend/openapi.json` and `frontend/src/lib/schema.d.ts` — search for any reference to `organization_id` on user-shaped schemas; should be gone

- [ ] Run the full gate trio: `make lint`, `make test`, `make openapi`. All must pass.

- [ ] End-to-end manual verification (browser, both servers running):
  - Promote your local Hanko user to superadmin via the Phase 01 CLI
  - As superadmin, create two orgs (Acme Capital, Bridgeview) each with a different founding admin
  - Sign in as Acme's admin → verify only Acme appears in the switcher
  - Acme's admin invites your superadmin's email (with a different role on Acme) → accept the invite while signed in as superadmin → switcher now shows both orgs PLUS the superadmin "manage all" link
  - Verify cross-org isolation: switch to Bridgeview, confirm Acme's funds/investors are not visible
  - Verify role-based UI: in Acme switch role to LP via the superadmin console, confirm the sidebar nav reflects LP scope
  - Document any gaps in `Auto Run Docs/2026-04-30-Edenscale-2/Working/e2e-verification.md`

- [ ] Write a short ADR capturing the architectural shift:
  - Create `docs/decisions/adr-NNN-multi-org-memberships.md` (find the next ADR number by listing `docs/decisions/`) with YAML front matter:
    ```yaml
    ---
    type: decision
    title: Multi-Org Memberships and Superadmin Role
    created: 2026-04-30
    tags: [auth, rbac, organizations]
    related:
      - "[[Hanko-Auth-Flow]]"
    ---
    ```
  - Capture: context (single-org → multi-org need), decision (`user_organization_memberships` join with per-org role + `superadmin` global role + `X-Organization-Id` header), alternatives considered (URL-scoped vs header), consequences (every org-scoped query now MUST resolve via active membership). Use `[[Document-Name]]` wiki-links to related architecture docs if any exist (look in `docs/architecture/`).
