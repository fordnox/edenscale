# Phase 07: Invitations UI

This phase replaces the old synchronous "create user" invite flow with the new token-based invitations from Phase 04. Admins (per-org) and superadmins (any org) get an updated invite dialog that sends an emailed invitation. New users land on `/invitations/accept?token=...` after signing in via Hanko, see a confirmation screen with the org name + role, and click Accept. Anyone signing in with a pending invitation also sees a banner from `/invitations/pending-for-me` so they don't miss it.

## Tasks

- [x] Read the existing invite UX so the rewrite preserves working pieces:
  - `frontend/src/pages/OrganizationSettingsPage.tsx` (the `InviteUserDialog` component)
  - The new generated types: open `frontend/src/lib/schema.d.ts` and grep for `InvitationCreate`, `InvitationRead`, `InvitationStatus` to confirm Phase 04 published the schema
  - `frontend/src/hooks/useApiMutation.ts` for the mutation idiom

  **Notes from review (2026-05-01):**
  - `OrganizationSettingsPage.tsx` (650 lines) currently houses an `InviteUserDialog` that posts to `POST /users` with `{ first_name, last_name, email, phone, title, role, organization_id }`. The dialog supports a superadmin org-picker via the `canChooseOrganization` prop (currently passed when `isAdmin` is true — note: the prop is misnamed, it gates on admin not superadmin; rewrite should switch to a real `isSuperadmin` check). Role select offers `admin | fund_manager | lp` (no superadmin option already — keep that constraint).
  - `frontend/src/lib/schema.d.ts` confirms Phase 04 published the schema:
    - `InvitationCreate { organization_id, email, role }` — POST `/invitations` returns `InvitationRead` (201). Header `X-Organization-Id` accepted.
    - `InvitationListItem` — used by `GET /invitations` (supports `status_filter` query, `X-Organization-Id` header).
    - `InvitationRead` — full record incl. `token`, `status`, `expires_at`, `invited_by_user_id`, `accepted_at`, `organization` (embedded `OrganizationRead`).
    - `InvitationStatus = "pending" | "accepted" | "revoked" | "expired"`.
    - `InvitationAccept { token }` — POST `/invitations/accept` returns `MembershipRead`.
    - `GET /invitations/pending-for-me` returns `InvitationRead[]` (no params).
    - `POST /invitations/{invitation_id}/{revoke,resend}` returns `InvitationRead`.
    - **No preview endpoint** — accept page should render generic copy per task #4.
  - `useApiMutation.ts` — wraps `openapi-fetch` client with TanStack Query; usage idiom: `useApiMutation("post", "/invitations", { onSuccess: ... }).mutate({ body, params, headers })`. Errors auto-surface via the api client middleware.

- [ ] Update the `InviteUserDialog` in `OrganizationSettingsPage.tsx`:
  - Drop the first/last name/phone/title fields — the new flow only collects `email` and `role` (the user fills out their profile after accepting)
  - Switch the mutation from `POST /users` to `POST /invitations` with `{ email, role, organization_id: <active org from useActiveMembership> }`
  - On success: toast "Invitation sent. {email} will receive an email to join."
  - For superadmins: keep the org-picker in the dialog (so a superadmin in the OrganizationSettingsPage can still invite to other orgs — though the more common path is the superadmin console)
  - Block selecting `superadmin` as a role in the dialog (the option must not appear; superadmin is CLI-only)

- [ ] Add a "Pending invitations" section to OrganizationSettingsPage:
  - Below the existing "Team" card, add a "Pending invitations" Card listing rows from `GET /invitations`
  - Columns: email, role (badge), invited_by (lookup user), expires_at (relative time), status, actions (Resend / Revoke)
  - Resend → `POST /invitations/{id}/resend`; Revoke → `POST /invitations/{id}/revoke`; both with optimistic toasts
  - Hide the section if the active membership role is not `admin` (LPs and fund managers don't need to see it)

- [ ] Build the accept page:
  - Create `frontend/src/pages/InvitationAcceptPage.tsx` rendered at `/invitations/accept` (route lives outside `AppShell` so it's chrome-free, but it DOES require a Hanko session — if not signed in, redirect to `/login?next=/invitations/accept?token=...`)
  - On mount: parse `token` from URL search params; call a small `GET /invitations/preview?token=...` endpoint OR (simpler) just render a generic "You're being invited to join an organization" card with an Accept button that calls `POST /invitations/accept`. If the backend doesn't have a preview endpoint, add one to Phase 04 retroactively only if absolutely necessary; otherwise show generic copy
  - On accept success: invalidate `/users/me/memberships`, set the new org as the active org via `setActiveOrganizationId`, toast "Welcome to {org name}", navigate to `/`
  - On error (expired, revoked, already accepted): show a clear card with the reason and a "Back to home" link

- [ ] Add a pending-invitation banner to the AppShell:
  - In `frontend/src/layouts/AppShell.tsx`, fetch `GET /invitations/pending-for-me`. If `data.length > 0`, render a thin top banner above the Topbar that says "You have {n} pending invitation(s). Review →" linking to a list page or opening a dialog showing each invitation with Accept / Decline buttons
  - The banner is dismissible per session (state in the provider, NOT localStorage — they should see it next time they sign in)
  - For users with zero memberships and at least one pending invite, the banner should be the dominant call-to-action (visually emphasize and skip the "no organization" empty state from Phase 05)

- [ ] Add the route in `App.tsx`:
  - `<Route path="/invitations/accept" element={<InvitationAcceptPage />} />` — outside the `AppShell` route group so it's standalone, but the page itself should render its own minimal frame

- [ ] Type checks and browser smoke test:
  - `cd frontend && pnpm run lint`
  - Run the full demo flow: superadmin creates org A with admin alice@example.com → alice signs in via Hanko → alice's `/users/me/memberships` shows A → alice invites bob@example.com as fund_manager → bob receives email (or, in dev, copy the token from the DB) → bob signs in fresh → accept page appears → bob clicks Accept → bob's switcher now shows org A
  - Document any gaps observed in `Auto Run Docs/2026-04-30-Edenscale-2/Working/invitations-followups.md`
