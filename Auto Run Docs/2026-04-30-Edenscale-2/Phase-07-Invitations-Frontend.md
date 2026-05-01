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

- [x] Update the `InviteUserDialog` in `OrganizationSettingsPage.tsx`:
  - Drop the first/last name/phone/title fields — the new flow only collects `email` and `role` (the user fills out their profile after accepting)
  - Switch the mutation from `POST /users` to `POST /invitations` with `{ email, role, organization_id: <active org from useActiveMembership> }`
  - On success: toast "Invitation sent. {email} will receive an email to join."
  - For superadmins: keep the org-picker in the dialog (so a superadmin in the OrganizationSettingsPage can still invite to other orgs — though the more common path is the superadmin console)
  - Block selecting `superadmin` as a role in the dialog (the option must not appear; superadmin is CLI-only)

  **Notes from implementation (2026-05-01):**
  - Replaced `canChooseOrganization` prop (was misnamed — gated on `isAdmin`) with `isSuperadmin`, sourced from `me?.role === "superadmin"` in `OrganizationSettingsContent`. Active-org users (admins/fund managers) no longer see the picker — invites always target their active org.
  - Dialog now collects only `email` + `role`; submits to `POST /invitations` with `{ email, role, organization_id }`. The api client middleware already attaches `X-Organization-Id` automatically, so no explicit header was added.
  - Introduced `type InvitableRole = Exclude<UserRole, "superadmin">` and a `INVITABLE_ROLES` const (`admin | fund_manager | lp`) to make the "no superadmin" rule a type-level guarantee, not just a runtime omission.
  - Success toast pulls the email from the response (`data.email`) so it reflects what the backend persisted (e.g. lowercased), rather than the form input.
  - Invalidates `["/invitations"]` so the upcoming "Pending invitations" section (next task) will see fresh data once added.
  - `pnpm run lint` (tsc --noEmit) passes.

- [x] Add a "Pending invitations" section to OrganizationSettingsPage:
  - Below the existing "Team" card, add a "Pending invitations" Card listing rows from `GET /invitations`
  - Columns: email, role (badge), invited_by (lookup user), expires_at (relative time), status, actions (Resend / Revoke)
  - Resend → `POST /invitations/{id}/resend`; Revoke → `POST /invitations/{id}/revoke`; both with optimistic toasts
  - Hide the section if the active membership role is not `admin` (LPs and fund managers don't need to see it)

  **Notes from implementation (2026-05-01):**
  - New `useApiQuery("/invitations")` is gated on `orgId !== null && isAdmin`, so the request is only fired for admins of the active org. The api client middleware auto-attaches `X-Organization-Id`, so the backend scopes results without any explicit header. Fund managers and LPs never see the card or the request.
  - The card lists *all* invitations (pending + historical) rather than filtering server-side to `status=pending`. The section is named "Pending invitations" because that's the day-to-day use case, but admins also benefit from seeing recent revoked/expired/accepted ones for context. The status column carries its weight only because of this choice; if we ever filter to pending, drop the column.
  - Sort is client-side: pending first, then most recently created. This keeps actionable rows at the top regardless of how the backend orders them.
  - `invited_by` is a lookup against the existing `usersQuery.data` (`/users`), which is already loaded for admins/fund managers — built into a `Map<number, UserRead>` via `useMemo`. Falls back to "—" if the inviter isn't in the team list (e.g. superadmin invitations).
  - Relative-time uses the existing `formatRelativeDays` helper (day-granularity is fine for 7-day token expiries).
  - Status → tone mapping: pending=warning (brass), accepted=active (conifer), revoked=muted, expired=negative.
  - Per-row mutation state: each Resend / Revoke button only spins for *that* row by checking `mutation.variables?.params.path.invitation_id === invitation.id`. Both buttons in a row disable while either is in flight to prevent double-clicks.
  - Actions cell shows "—" for non-pending rows (only pending invitations can be resent/revoked per backend rules).
  - The toasts pull `data.email` from the response (so they reflect normalized email casing).
  - Both mutations invalidate `["/invitations"]` on success so the table refreshes immediately.
  - `pnpm run lint` (tsc --noEmit) passes.

- [x] Build the accept page:
  - Create `frontend/src/pages/InvitationAcceptPage.tsx` rendered at `/invitations/accept` (route lives outside `AppShell` so it's chrome-free, but it DOES require a Hanko session — if not signed in, redirect to `/login?next=/invitations/accept?token=...`)
  - On mount: parse `token` from URL search params; call a small `GET /invitations/preview?token=...` endpoint OR (simpler) just render a generic "You're being invited to join an organization" card with an Accept button that calls `POST /invitations/accept`. If the backend doesn't have a preview endpoint, add one to Phase 04 retroactively only if absolutely necessary; otherwise show generic copy
  - On accept success: invalidate `/users/me/memberships`, set the new org as the active org via `setActiveOrganizationId`, toast "Welcome to {org name}", navigate to `/`
  - On error (expired, revoked, already accepted): show a clear card with the reason and a "Back to home" link

  **Notes from implementation (2026-05-01):**
  - Took the simpler path — no preview endpoint, just generic "You're being invited to join an organization" copy with a `MailCheck` icon, an "Accept invitation" primary button, and a "Not now" ghost link. The org name only appears post-accept (in the toast and via the active-org switcher), which is fine: the email already named the org, and a preview endpoint would have meant adding an unauthenticated route on the backend just to render one phrase.
  - The page renders its own minimal frame (centered card on `bg-page`, max-width `lg`, `min-h-svh`) since the task #5 route will mount it outside `AppShell`. No sidebar/topbar/breadcrumbs.
  - Auth gate: uses `useAuth()` and redirects unauth'd users to `/login?next=<encoded /invitations/accept?token=...>` via `navigate(..., { replace: true })`. While `useAuth` is still loading or the redirect is firing, renders a centered spinner (avoids a flicker of the accept card before the bounce).
  - **Updated `LoginPage.tsx`** to honor the `?next=` query param — without that change the round trip would dead-end on `/`. Added a `safeNextPath()` guard that only accepts paths starting with a single `/` (rejects `//foo` and absolute URLs) to prevent open-redirects. Both the `isAuthenticated` effect and the `hanko.onSessionCreated` listener now `navigate(nextPath, { replace: true })`.
  - On `POST /invitations/accept` success: invalidates both `["/users/me/memberships"]` and `["/users/me"]` (the `me` query also seeds isSuperadmin / role display), calls `setActiveOrganizationId(data.organization_id)` so the AppShell sees the new org immediately on mount, toasts "Welcome to {org}.", then `navigate("/")`. The active-org effect in `ActiveOrganizationContext` will reconcile once memberships refetch, but our optimistic set keeps the UI smooth in the interim.
  - Error handling: declared an `onError` that pulls `error.detail` (the FastAPI `HTTPException` shape — 404 not found / 403 wrong user / 410 already-accepted/revoked/expired) into a state-held `errorMessage`, and renders an `EmptyState` card with that message + a "Back to home" link. Falls back to a generic message if `detail` isn't a string. The api.ts middleware will *also* fire its global "Request failed" toast for the same error — accepted that as a known minor UX papercut (toast = transient ack, card = persistent context); fixing it would require a cross-cutting middleware change to suppress per-request, which felt out of scope.
  - Token-missing edge case: if `?token=` is absent from the URL, renders an EmptyState explaining the link is malformed rather than firing the mutation with an empty string.
  - `cd frontend && pnpm run lint` (tsc --noEmit) passes.
  - **Out of scope for this task** (covered by task #5): wiring the route into `App.tsx`. The page exists but won't render until that route is added.

- [x] Add a pending-invitation banner to the AppShell:
  - In `frontend/src/layouts/AppShell.tsx`, fetch `GET /invitations/pending-for-me`. If `data.length > 0`, render a thin top banner above the Topbar that says "You have {n} pending invitation(s). Review →" linking to a list page or opening a dialog showing each invitation with Accept / Decline buttons
  - The banner is dismissible per session (state in the provider, NOT localStorage — they should see it next time they sign in)
  - For users with zero memberships and at least one pending invite, the banner should be the dominant call-to-action (visually emphasize and skip the "no organization" empty state from Phase 05)

  **Notes from implementation (2026-05-01):**
  - New `PendingInvitationsBannerProvider` (`frontend/src/contexts/PendingInvitationsBannerContext.tsx`) holds two pieces of in-memory session state: `bannerDismissed: boolean` (whole-banner dismiss) and `declinedIds: Set<number>` (per-invitation local dismissals). Provider wraps the app inside `App.tsx` between `ActiveOrganizationProvider` and the routes — so it sits across both `/login` and the AppShell routes. State resets on hard reload (which is what "see it next time they sign in" means in practice).
  - `AppShell.tsx` fires `useApiQuery("/invitations/pending-for-me", undefined, { enabled: isAuthenticated })`, gated on `useAuth().isAuthenticated` so unauthenticated visits don't fire the request. Filters out `declinedIds` client-side. Uses 60s `staleTime` to avoid refetching on every nav.
  - The banner is rendered above the Topbar inside the right pane (not full-width across the sidebar), so it aligns with the topbar visually. Brass palette (`bg-brass-50`, `border-brass-100`, `text-brass-700`) — the same warm yellow we use for the "warning"/draft tone elsewhere. Thin (py-2). Has a Review button (opens dialog) and a dismiss X.
  - "Emphasize" mode for users with `memberships.length === 0`: a thicker bottom border (`border-b-2`) and bolder copy. The inline CTA color stays the same since the whole banner is already the dominant element on screen at that point. We could go further (gradient, accent stripe) if user feedback says it's still missable.
  - The "no organization yet" empty-state condition adds `&& !hasPendingInvitations` so users with pending invites land directly on the dashboard `<Outlet />` (instead of an empty card) and the banner sits at the top as the dominant CTA. The Outlet itself will be sparsely populated for them (most queries 403/404 without an active org), but the banner's "Review" CTA is right there.
  - **Decline UX trade-off:** there's no backend `/invitations/decline` endpoint (the Phase 04 schema only exposes admin-side `revoke` + invitee-side `accept`). Rather than retroactively adding one, "Decline" is implemented as a per-session client-side dismissal — it adds the invitation ID to `declinedIds`, which filters it out of the banner count and dialog list. The invitation will expire on its own (7-day TTL) or can be revoked by the inviter. If we ever want a real decline (e.g. to free up the email for re-invite at a different role), Phase 04 should grow a `POST /invitations/decline` endpoint and the dialog wires up to it instead of `decline(id)`.
  - Dialog (`PendingInvitationsDialog.tsx`) shows each invitation as a card row: organization name (bold), role badge, "Expires {relative}". Accept/Decline buttons on the right. Single shared `useApiMutation("post", "/invitations/accept")` — per-row spinner is keyed by comparing `acceptMutation.variables?.body.token === invitation.token`. All other rows disable while a request is in flight to prevent double-clicks across rows.
  - Accept success mirrors the `InvitationAcceptPage` flow: invalidates `/users/me/memberships`, `/users/me`, and `/invitations/pending-for-me`; calls `setActiveOrganizationId(data.organization_id)` to switch to the new org optimistically; toasts "Welcome to {org}". The dialog stays open if there are more pending invitations, so the user can accept multiple in one session. When the last invitation is dealt with (accepted or declined), the banner unmounts with the dialog inside it — small UX papercut (abrupt close); fixing it would require hoisting the dialog out of the banner component, which felt premature.
  - `cd frontend && pnpm run lint` (tsc --noEmit) passes; `pnpm run build` produces a clean prod bundle. **Did NOT browser-test the live UX** — this Maestro run had no browser harness available; the next task (#5: wire `/invitations/accept` route + smoke test) is the natural place to do an end-to-end flow including this banner.

- [ ] Add the route in `App.tsx`:
  - `<Route path="/invitations/accept" element={<InvitationAcceptPage />} />` — outside the `AppShell` route group so it's standalone, but the page itself should render its own minimal frame

- [ ] Type checks and browser smoke test:
  - `cd frontend && pnpm run lint`
  - Run the full demo flow: superadmin creates org A with admin alice@example.com → alice signs in via Hanko → alice's `/users/me/memberships` shows A → alice invites bob@example.com as fund_manager → bob receives email (or, in dev, copy the token from the DB) → bob signs in fresh → accept page appears → bob clicks Accept → bob's switcher now shows org A
  - Document any gaps observed in `Auto Run Docs/2026-04-30-Edenscale-2/Working/invitations-followups.md`
