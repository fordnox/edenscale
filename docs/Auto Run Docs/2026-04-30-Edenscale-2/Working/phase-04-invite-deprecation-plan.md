---
type: analysis
title: Phase 04 — POST /users Deprecation Plan
created: 2026-05-01
tags:
  - phase-04
  - invitations
  - deprecation
related:
  - '[[Phase-04-Invitations-Backend]]'
  - '[[Phase-07-Invitations-Frontend]]'
  - '[[Phase-08-Legacy-Cleanup-And-E2E]]'
---

# Phase 04 — `POST /users` Deprecation Plan

Audit of the existing synchronous invite UX so the new token-based flow
(`POST /invitations`) can land cleanly without breaking the current admin
dialog. Phase 07 swaps the frontend mutation; Phase 08 deletes the route.

## Current synchronous invite path

### Backend (`backend/app/routers/users.py:84-109`)

`POST /users` (`invite_user`):

- Auth: `require_membership_roles(admin, fund_manager, superadmin)` — uses the
  active membership returned by Phase 02 RBAC.
- Hard-blocks the synthesized superadmin path (`membership.id is None`) with a
  400 redirecting to a future `/organizations/{id}/memberships` route. With
  the Phase 04 plan, the redirect target becomes `POST /invitations` instead;
  the `detail` string was updated in this commit to reflect that.
- Body: `UserCreate` (first/last name, email, phone, title, role,
  organization_id). `organization_id` is overwritten to
  `membership.organization_id` server-side, so admins can only invite into
  their active org.
- 409 on existing email; otherwise creates a `User` row immediately via
  `UserRepository.create`. **No email is sent** — the invitee just shows up
  signed in via Hanko on first login because `get_current_user_record`
  upserts by email.
- Response: full `UserRead`.

### Frontend dialog (`frontend/src/pages/OrganizationSettingsPage.tsx`)

`InviteUserDialog` (lines 422-644):

- Calls `useApiMutation("post", "/users", …)` with the full `UserCreate`
  body. Phase 07 will swap this to `useApiMutation("post", "/invitations",
  …)` with the much smaller `InvitationCreate` body
  (`{ email, role, organization_id }`).
- Collects fields the new flow does NOT need: `first_name`, `last_name`,
  `phone`, `title`. Phase 07 should drop these from the dialog; the invitee
  fills them in via `PATCH /users/me` after accepting.
- The "Organization" select stays, but only for superadmins (the admin path
  derives it from active membership). Phase 07 keeps the same gating logic.
- Success toast `"User invited"` — Phase 07 should change to
  `"Invitation sent"` to reflect that delivery is now async.

## Why deprecate vs. delete now

- The invite dialog still calls `POST /users` until Phase 07 ships. Removing
  the route now would break the deployed UI.
- The OpenAPI client (`frontend/src/lib/schema.d.ts`) imports the type. Even
  if the frontend isn't called, removing the route would eliminate the type
  and break compilation.
- Marking `deprecated=True` shows up in `/openapi.json` and the generated
  client without changing runtime behavior; admins still get the synchronous
  path, frontend keeps working, and the Swagger UI surfaces the warning.

## Changes made in this task

1. `backend/app/routers/users.py:84-92` — added `deprecated=True` to the
   route decorator and a docstring pointing at Phase 04 / Phase 07.
2. `backend/app/routers/users.py:99` — updated the existing 400 detail
   string to reference `POST /invitations` (the actual successor) instead
   of the never-implemented `POST /organizations/{id}/memberships`.

No schema or behavior changes: the route still accepts the same body, still
returns the same `UserRead`, and is still mounted under `/users` in
`backend/app/main.py:68-73`.

## What Phase 04 will add (preview, not built yet)

- `OrganizationInvitation` model + `InvitationStatus` enum
- `backend/app/schemas/organization_invitation.py`
- `backend/app/repositories/organization_invitation_repository.py`
- `backend/app/services/hanko.py` — calls Hanko admin API to deliver the email
- `backend/app/routers/invitations.py` mounted at `/invitations`
- Alembic migration + tests

## What Phase 07 will swap on the frontend

- `useApiMutation("post", "/users", …)` → `useApiMutation("post",
  "/invitations", …)` with `{ email, role, organization_id }` body.
- Drop name / phone / title fields from the invite dialog.
- Add a "pending invitations" table backed by `GET /invitations` with
  revoke / resend buttons.
- Add a banner consuming `GET /invitations/pending-for-me` for invitees
  who land in the app before accepting.

## What Phase 08 will delete

- `POST /users` route + the `UserCreate.organization_id` field that exists
  only to support the synchronous create-from-invite case.
- `tests/test_users_router.py` cases targeting the deprecated route.

## Verification

`make openapi` was run after the edit; `backend/openapi.json` now carries
`"deprecated": true` on the `POST /users` operation, and the generated
`frontend/src/lib/schema.d.ts` reflects the same.
