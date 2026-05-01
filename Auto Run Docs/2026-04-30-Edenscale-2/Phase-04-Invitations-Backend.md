# Phase 04: Invitations Backend (Send + Accept)

This phase builds the invitation system. Admins of an org (or superadmins acting on any org) can invite a person by email + role. The platform creates a pending invitation, asks Hanko to send the email (Hanko owns email delivery), and exposes an accept endpoint that the invited user hits after they sign in. On accept, a `user_organization_memberships` row is created with the invited role; the existing `get_current_user_record` already auto-creates a `User` row on first Hanko sign-in, so the accept flow just attaches a membership.

## Tasks

- [x] Read the existing invite UX in `backend/app/routers/users.py` (`invite_user`) and the frontend's existing invite dialog in `frontend/src/pages/OrganizationSettingsPage.tsx`. The new system replaces the synchronous "create user row" approach with a token-based pending invitation. Plan to deprecate (but not delete) `POST /users` — Phase 07 swaps the frontend dialog over.
  - Audited `backend/app/routers/users.py:84-109` and `frontend/src/pages/OrganizationSettingsPage.tsx:422-644`; full call-path notes in `Auto Run Docs/2026-04-30-Edenscale-2/Working/phase-04-invite-deprecation-plan.md`.
  - Marked `POST /users` with FastAPI `deprecated=True` and added a docstring pointing at `POST /invitations` (Phase 04) and the Phase 07 frontend swap. The deprecation flag now flows through `backend/openapi.json` and `frontend/src/lib/schema.d.ts` (`@deprecated` on the `post` operation under `"/users"`).
  - Updated the existing `400` detail string for the synthesized-superadmin guard from `POST /organizations/{id}/memberships` to the actual successor `POST /invitations`.
  - Verified: `make openapi` regenerated cleanly, `make lint` passed, and the 11 user-scoped pytest cases still pass — no behavior change, just OpenAPI metadata.

- [x] Add the `OrganizationInvitation` model:
  - Created `backend/app/models/organization_invitation.py` with all required columns. `expires_at` uses a Python-side `default=_default_invitation_expiry` callable (`now(UTC) + 14 days`) so it stays portable across SQLite (dev) and Postgres (prod). `invited_by_user_id` is nullable for superadmin auto-invites; `invited_by` relationship is one-way (no `User.sent_invitations` back-ref needed yet — Phase 04 routers + tests can add it if surface area calls for it).
  - Added `InvitationStatus(str, enum.Enum)` to `backend/app/models/enums.py` with `pending`/`accepted`/`revoked`/`expired`. The `superadmin` role rejection lives at the schema layer (next checkbox).
  - Wired `Organization.invitations` back-ref with `cascade="all, delete-orphan"` to mirror `memberships`.
  - Registered the new model + enum in `backend/app/models/__init__.py` so `make lint`'s import smoke test sees them and Alembic autogenerate (next migration checkbox) picks up the table.
  - Verified: `make lint` clean and the full pytest suite (215 tests) still passes — pure additive change.

- [x] Schemas + repository:
  - `backend/app/schemas/organization_invitation.py` with `InvitationCreate` (email, role, organization_id), `InvitationRead` (full record + nested `organization: OrganizationRead`), `InvitationAccept` (just `token`), and `InvitationListItem` for table views
  - `backend/app/repositories/organization_invitation_repository.py` with: `create`, `get_by_token`, `list_for_organization`, `list_pending_for_email`, `mark_accepted`, `mark_revoked`, `expire_stale` (helper for a future cron — write the function but don't schedule it yet)
  - The schema layer enforces the "no `superadmin` role via invite" rule via a `field_validator` on `InvitationCreate.role` (matches the model-doc note); `InvitationAccept` caps token length at 128 to mirror the column.
  - Repo also gained `get(invitation_id)` and `rotate_token(invitation_id)` because the upcoming router checkboxes (revoke / resend) need them — kept them right next to the rest of the contract so the router stays a thin shim.
  - `expire_stale` accepts an optional `now` arg so future cron tests can pass a frozen clock without monkey-patching `datetime`. Bulk update uses `synchronize_session=False` per the same pattern in `NotificationRepository.mark_all_read`.
  - Token generator: `secrets.token_urlsafe(48)` (~64 chars) reusing the pattern from `routers/documents.py:42`; well under the `String(128)` column.
  - Wired the four schemas into `app/schemas/__init__.py` and the repository into `app/repositories/__init__.py` so the import smoke test in `make lint` covers them.
  - Verified: `make lint` passed (`ruff` reformatted one method signature onto a single line — kept), and the full pytest suite (215 tests) still green. No router or migration touched yet — those are the next two checkboxes.

- [x] Hanko email integration:
  - Confirmed via context7 (`/websites/hanko_io`) that Hanko has no arbitrary transactional email surface — the public API only sends authentication passcodes (`POST /passcode/login/initialize`, requires a Hanko `user_id`) and the `email.send` webhook fires only when *Hanko* needs to send an auth email. The Admin API at `{HANKO_API_URL}/admin` (Bearer API key) supports `GET /users?email=`, `POST /users` for create, etc. Existing repo had no Hanko HTTP calls — `core/auth.py` only validates JWTs against JWKS.
  - Took the documented fallback path: `send_invitation_email` looks up the invitee in Hanko (Admin API), creates them via `POST /admin/users` if missing (handles 409 race by re-fetching), then triggers `POST /passcode/login/initialize` so Hanko mails them an authentication passcode. Once they sign in, the Phase-07 frontend banner reads `/invitations/pending-for-me` and surfaces the actual invite — the `accept_url` is recorded for resend bookkeeping and for any future custom-email path.
  - Added `HANKO_API_KEY: str = ""` and `APP_DOMAIN_URL: str = "http://localhost:3000"` to `app/core/config.py` plus `.env.example`. Did not promote APP_DOMAIN to a full URL because `worker.py` and `openrouter.py` still consume it as a bare host.
  - Failure handling: returns `False` (never raises) on missing config, `httpx.HTTPError`, or `HankoServiceError`; logs at WARNING for the unconfigured fast-path and `logger.exception` for the API failure path so the router can keep `status='pending'` and let the admin resend.
  - Tests: `backend/tests/test_hanko_service.py` (6 cases) covers unconfigured short-circuit, existing-user happy path, missing-user create+passcode, 409 race fallback, HTTP error suppression, and `httpx.RequestError` suppression. `httpx.AsyncClient` is patched at the service-module boundary per the Phase-04 testing rule. All 221 backend tests still pass; `make lint` clean (ruff trimmed one method signature onto a single line — kept).
  - Note for the next checkbox (router): import the entry point as `from app.services.hanko import send_invitation_email` and treat `False` as "leave invitation pending; admin can resend".

- [x] Build the invitation router `backend/app/routers/invitations.py`:
  - All six endpoints landed in `backend/app/routers/invitations.py`. Admin/superadmin-gated routes use `require_membership_roles(UserRole.admin, UserRole.superadmin)` — superadmins acting through a synthesized membership pass the role check; a `_ensure_can_act_on_org` helper then 403s non-superadmins acting on a different org. `data.organization_id` is matched against the active membership's org so admins cannot quietly invite into someone else's tenant when they hold multiple memberships.
  - `POST /invitations` resolves the target org, lower-cases the email before storing (Pydantic `EmailStr` does not normalize), persists via the repo, and `await`s `send_invitation_email`. The Hanko service already swallows failures internally, so the row stays `pending` and the admin can resend.
  - `POST /invitations/accept` requires the JWT email to match the invitation row (case-insensitive). Status checks: `accepted`/`revoked`/`expired` → 410. Inline expiry check on `expires_at` flips status to `expired` and 410s — keeps the row consistent without waiting for the (unscheduled) cron. Idempotency for re-accepts is covered by the 410 on `accepted`. If the user already has a membership in the org we update the role rather than inserting a duplicate — needed because seeded `lp` users could re-accept into a higher role.
  - `POST /{id}/revoke` and `POST /{id}/resend` 409 (not 400) when the invitation isn't `pending` — different invariant from "bad request"; the admin should refresh the list. `resend` calls `repo.rotate_token` so the old email link stops working before re-sending.
  - `GET /pending-for-me` uses `get_current_user_record` and matches `current_user.email` (lower-cased) against the repo helper. Empty email returns `[]` rather than erroring — fresh `get_current_user_record` provisioning may yield empty when the JWT lacks an `email` claim.
  - Route ordering: `/pending-for-me` and `/accept` are declared before the `/{invitation_id}/...` routes so FastAPI's path matching picks the static paths first.
  - Uses `settings.APP_DOMAIN_URL` to build `accept_url` (recorded in the Hanko log line per the service contract — Hanko cannot embed it in the auth-passcode email).
  - Verified: `make lint` passes (a few SQLAlchemy `Column[T]` vs typed-arg friction needed `# type: ignore[invalid-argument-type]` per the codebase pattern); the existing 221 backend tests still pass — pure additive change, no mounting yet (next checkbox).

- [x] Mount the router in `backend/app/main.py` under `/invitations` with `Depends(get_current_user)`. Per-route deps handle membership/superadmin checks.
  - Added `invitations` to the `app.routers` import block (alphabetical between `investors` and `notifications`) and registered `app.include_router(invitations.router, prefix="/invitations", tags=["invitations"], dependencies=[Depends(get_current_user)])` immediately after `superadmin` so the org/user-management routers cluster together.
  - Verified: `make openapi` regenerated and all five distinct invitation paths show up (`POST/GET /invitations`, `/invitations/pending-for-me`, `/invitations/accept`, `/invitations/{invitation_id}/revoke`, `/invitations/{invitation_id}/resend`); `frontend/src/lib/schema.d.ts` picked them up. `make lint` clean and the full pytest suite (221 tests) still passes.

- [x] Migration:
  - Autogenerated `backend/app/alembic/versions/20260501_0509_7a3259f3e3bb_add_organization_invitations.py`. Alembic detected the new `organization_invitations` table plus all four indexes (email, invited_by_user_id, organization_id, and the unique token index). The two `sa.Enum` columns (`invitation_role` for the reused `UserRole` values, `invitation_status` for the new pending/accepted/revoked/expired set) render as VARCHAR on SQLite and as `CREATE TYPE ... AS ENUM` on PostgreSQL implicitly via `op.create_table`.
  - Hand-edit: reformatted the autogenerated body for readability, then added a PostgreSQL-only `DROP TYPE IF EXISTS invitation_status` / `DROP TYPE IF EXISTS invitation_role` block to `downgrade()` so the implicit enum types get cleaned up and a re-upgrade can recreate them. Mirrors the membership-role pattern in `20260430_2257_ee0cff22bcfc`. SQLite is a no-op on that branch.
  - Verified idempotent re-application against the dev SQLite DB: `make upgrade` → table + 4 indexes present, `make downgrade` → table dropped cleanly, `make upgrade` again → table + indexes recreated identically. `make lint` clean and the full pytest suite (221 tests) still passes.

- [ ] Tests:
  - `backend/tests/test_invitations_router.py`:
    - admin creates invite → row exists, email service called (mock the Hanko service)
    - non-admin gets 403 on POST/list/revoke
    - superadmin can invite to any org
    - signed-in invitee accepts → membership created, status flipped, second accept attempt 410
    - revoke + resend flows work
    - `pending-for-me` returns invitations matching the JWT email
  - `backend/tests/test_invitation_repository.py`: covers the helper methods including `expire_stale`
  - Mock the Hanko HTTP client at the service-module boundary — do NOT hit the real Hanko API

- [ ] Search the codebase for any TODO/HACK markers left over from older invite logic and clean them up if related.

- [ ] Final gate trio: `make openapi`, `make lint`, `make test`. The frontend `schema.d.ts` will gain `InvitationRead`, `InvitationCreate`, `InvitationStatus` etc., which Phase 07 consumes.
