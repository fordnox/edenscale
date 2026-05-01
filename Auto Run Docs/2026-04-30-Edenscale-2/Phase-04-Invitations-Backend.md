# Phase 04: Invitations Backend (Send + Accept)

This phase builds the invitation system. Admins of an org (or superadmins acting on any org) can invite a person by email + role. The platform creates a pending invitation, asks Hanko to send the email (Hanko owns email delivery), and exposes an accept endpoint that the invited user hits after they sign in. On accept, a `user_organization_memberships` row is created with the invited role; the existing `get_current_user_record` already auto-creates a `User` row on first Hanko sign-in, so the accept flow just attaches a membership.

## Tasks

- [x] Read the existing invite UX in `backend/app/routers/users.py` (`invite_user`) and the frontend's existing invite dialog in `frontend/src/pages/OrganizationSettingsPage.tsx`. The new system replaces the synchronous "create user row" approach with a token-based pending invitation. Plan to deprecate (but not delete) `POST /users` — Phase 07 swaps the frontend dialog over.
  - Audited `backend/app/routers/users.py:84-109` and `frontend/src/pages/OrganizationSettingsPage.tsx:422-644`; full call-path notes in `Auto Run Docs/2026-04-30-Edenscale-2/Working/phase-04-invite-deprecation-plan.md`.
  - Marked `POST /users` with FastAPI `deprecated=True` and added a docstring pointing at `POST /invitations` (Phase 04) and the Phase 07 frontend swap. The deprecation flag now flows through `backend/openapi.json` and `frontend/src/lib/schema.d.ts` (`@deprecated` on the `post` operation under `"/users"`).
  - Updated the existing `400` detail string for the synthesized-superadmin guard from `POST /organizations/{id}/memberships` to the actual successor `POST /invitations`.
  - Verified: `make openapi` regenerated cleanly, `make lint` passed, and the 11 user-scoped pytest cases still pass — no behavior change, just OpenAPI metadata.

- [ ] Add the `OrganizationInvitation` model:
  - Create `backend/app/models/organization_invitation.py` with columns: `id` (PK), `organization_id` (FK + index), `email` (str, indexed), `role` (`UserRole` enum, NOT NULL — but reject `superadmin` at the schema layer; superadmin assignment is CLI-only), `token` (str, unique, indexed; generate via `secrets.token_urlsafe(32)`), `status` (new enum `InvitationStatus` with `pending`, `accepted`, `revoked`, `expired`), `expires_at` (DateTime, default `now() + 14 days`), `invited_by_user_id` (FK `users.id`, nullable for superadmin auto-invites), `created_at`, `updated_at`, `accepted_at` (nullable)
  - Add `InvitationStatus` enum to `backend/app/models/enums.py`
  - Wire `Organization.invitations` relationship back-ref

- [ ] Schemas + repository:
  - `backend/app/schemas/organization_invitation.py` with `InvitationCreate` (email, role, organization_id), `InvitationRead` (full record + nested `organization: OrganizationRead`), `InvitationAccept` (just `token`), and `InvitationListItem` for table views
  - `backend/app/repositories/organization_invitation_repository.py` with: `create`, `get_by_token`, `list_for_organization`, `list_pending_for_email`, `mark_accepted`, `mark_revoked`, `expire_stale` (helper for a future cron — write the function but don't schedule it yet)

- [ ] Hanko email integration:
  - Search `backend/app/` for existing Hanko HTTP calls (the `auth.py` only validates JWTs — the platform may not yet call Hanko's admin API). Read the Hanko admin API docs if context7 has them: query `mcp__plugin_context7_context7__resolve-library-id` for `hanko` and then `query-docs` for the email/passcode/invitation endpoint
  - Add `backend/app/services/hanko.py` with `send_invitation_email(email: str, accept_url: str, organization_name: str, inviter_name: str | None)`. If Hanko's API can send arbitrary transactional emails, use it; if not, the realistic fallback is to use Hanko's "send passcode" flow against the email plus a magic-link callback URL — research first, then implement. Surface the `HANKO_API_URL` (and a new `HANKO_API_KEY` if needed) from `app.core.config.settings`
  - Construct `accept_url` as `f"{settings.APP_DOMAIN_URL}/invitations/accept?token={token}"` (add `APP_DOMAIN_URL` to config if not present — read `app/core/config.py` first)
  - On send failure, log and return the invitation anyway (status stays `pending`) so the admin can resend; do NOT raise to the client

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
