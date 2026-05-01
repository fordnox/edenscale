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

- [ ] Build the invitation router `backend/app/routers/invitations.py`:
  - `POST /invitations` — body `InvitationCreate`. Authorization: requires admin membership of the target org OR `require_superadmin`. Creates the row, calls Hanko send, returns `InvitationRead`
  - `GET /invitations` — list pending invitations for the active org (admin membership required)
  - `POST /invitations/accept` — body `{ token }`. Authenticated via `get_current_user_record` (the user must be signed in via Hanko). Validates token + status + expiry, creates the `user_organization_memberships` row (or updates role if one already exists), marks invitation accepted, returns the new `MembershipRead`
  - `POST /invitations/{invitation_id}/revoke` — admin/superadmin only; flips status to revoked
  - `POST /invitations/{invitation_id}/resend` — admin/superadmin only; re-issues a new token (invalidating the old one) and re-sends the email
  - `GET /invitations/pending-for-me` — uses the authenticated user's email to surface pending invitations (frontend banner in Phase 07)

- [ ] Mount the router in `backend/app/main.py` under `/invitations` with `Depends(get_current_user)`. Per-route deps handle membership/superadmin checks.

- [ ] Migration:
  - `cd backend && uv run alembic revision -m "add organization invitations" --autogenerate`
  - Verify the autogenerate creates the table and the new `invitation_status` enum; hand-edit if needed
  - Run `make upgrade` and confirm idempotent re-application (downgrade + upgrade)

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
