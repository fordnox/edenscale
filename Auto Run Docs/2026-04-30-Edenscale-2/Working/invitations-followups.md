---
type: note
title: Invitations Frontend Follow-ups
created: 2026-05-01
tags:
  - invitations
  - frontend
  - phase-07
  - followups
related:
  - '[[Phase-07-Invitations-Frontend]]'
  - '[[phase-04-invite-deprecation-plan]]'
---

# Invitations UI — Smoke-test Coverage & Follow-ups

Captured during Phase 07 task #7 ("Type checks and browser smoke test"). The
goal of that task was to run the full demo flow (superadmin → admin alice →
fund_manager bob) end-to-end. What actually shipped is documented below,
along with the gaps that still need a human-driven pass.

## What ran cleanly

- `cd frontend && pnpm run lint` (tsc --noEmit) — pass.
- Vite dev server boots without compile-time errors.
- Unauthenticated Playwright probe of the new accept route
  (`Working/invitations-smoke.py`):
  - `/invitations/accept?token=smoke-token-abc-123` → bounces to
    `/login?next=%2Finvitations%2Faccept%3Ftoken%3Dsmoke-token-abc-123`
    (i.e. the token round-trips through URL-encoding, exactly as designed
    in task #4 and the `LoginPage.tsx` `?next=` change).
  - `/invitations/accept` (no token) → bounces to
    `/login?next=%2Finvitations%2Faccept`. The "malformed link" empty-state
    is gated behind auth, so it can only be hit after sign-in; the no-token
    case in the unauth path correctly preserves the absent-token URL.
  - LoginPage renders without uncaught JS exceptions on either entry.

## What was NOT smoke-tested (gaps)

The plan in Phase-07 task #7 was a true end-to-end demo flow:

> superadmin creates org A with admin alice@example.com → alice signs in via
> Hanko → alice's `/users/me/memberships` shows A → alice invites bob@example.com
> as fund_manager → bob receives email (or, in dev, copy the token from the DB)
> → bob signs in fresh → accept page appears → bob clicks Accept → bob's
> switcher now shows org A.

None of the **authenticated** branches were exercised by an automated probe:

1. Admin path: invite-dialog mutation → POST `/invitations` →
   "Pending invitations" card row → resend / revoke optimism.
2. Invitee path: `/invitations/accept?token=…` after sign-in →
   `MailCheck` accept card → POST `/invitations/accept` → toast +
   active-org switch + redirect to `/`.
3. AppShell banner: `GET /invitations/pending-for-me` → top banner →
   "Review" dialog → Accept (or per-session Decline).
4. Zero-membership emphasis mode (banner becomes the dominant CTA when the
   user has no orgs but has pending invites — replaces the "no organization"
   empty state from Phase 05).

**Why deferred:** Hanko issues sessions via emailed magic links. Driving
those headlessly requires either (a) intercepting the email at an MTA we
own, (b) seeding a JWT directly via the Hanko admin API and grafting it
into `localStorage`, or (c) a dev-only test-mode auth bypass on the
backend. None of those exist in the repo today, and adding any of them is
out of scope for this autonomous run.

## Suggested next steps for a manual demo pass

The shipped pieces should hang together — every one of them was lint-clean
and individually code-reviewed during Phase 07 — but a human pass is still
the source of truth for UX. To run it locally:

1. Boot `make start-backend` + `make start-worker` + `make start-frontend`.
2. Promote a superadmin via `python -m app.cli promote-superadmin <email>`
   (Phase 06 console task), or check the README for the equivalent helper.
3. Sign in as the superadmin → `/superadmin/organizations` → create org A
   with admin = `alice@<domain>`.
4. Sign in as alice (use the magic link from the dev mailcatcher or copy
   the token from `users` / Hanko's local DB depending on dev setup).
5. As alice on `/organizations`, open the invite dialog → invite
   `bob@<domain>` as `fund_manager`. Confirm:
   - Invite dialog only collects email + role (no first/last/title/phone).
   - Role select shows admin / fund_manager / lp (no superadmin).
   - "Pending invitations" card lists Bob with status=pending,
     resend / revoke buttons enabled.
6. As bob (fresh sign-in), open `/invitations/accept?token=<bob_token>`:
   - If unauth, you should land on `/login?next=…`; after Hanko sign-in,
     the `?next=` round-trip should drop you back on the accept page.
   - Click Accept → toast "Welcome to {org}." → router navigates to `/`,
     org switcher shows the new org as active.
7. Re-sign-in bob with another pending invitation queued → confirm the
   AppShell top banner appears, Review dialog lists the invite, Accept
   works, banner disappears once the list is empty.
8. Revoke a pending invitation as alice → Bob's banner / accept page should
   show the "We couldn't accept this invitation" empty state (with the
   backend's `detail` message surfaced).

## Known UX papercuts (intentional)

These came up during implementation and were left as-is — listed here so a
future ramp can decide whether to address them:

- **Accept-error double-surface.** On accept failure (404/403/410), the
  page shows a persistent EmptyState card *and* the api.ts middleware
  fires its global "Request failed" toast for the same error. The toast
  is transient and arguably redundant. Suppressing it requires a
  cross-cutting middleware change (per-request opt-out flag); deferred.
- **No real "decline" endpoint.** The pending-invitations dialog's
  "Decline" button is a per-session client-side dismissal (filters via
  `declinedIds` in `PendingInvitationsBannerContext`). Backend Phase 04
  only exposed admin-side `revoke` and invitee-side `accept`. If we ever
  want a true decline (so the invitee can free up the slot for a
  different role, or stop the email reminders), Phase 04 should grow
  `POST /invitations/decline` and the dialog should switch to it.
- **Banner unmounts mid-Decline of last item.** When the user declines or
  accepts the very last pending invitation, the banner unmounts — and the
  dialog inside it unmounts with it, which is mildly abrupt. Hoisting the
  dialog up to the layout level would fix it but felt premature.
- **Banner emphasis mode is subtle.** For zero-membership users we add a
  thicker bottom border and slightly bolder copy. If feedback says the
  banner is still missable in that state, escalate to a brass gradient or
  an accent stripe.
- **No preview endpoint on accept page.** The org name only appears in
  the success toast and via the active-org switcher post-accept — not
  pre-accept. A `GET /invitations/preview?token=…` (unauth) endpoint
  would let the page render "Join {Org X} as {role}" copy *before* the
  accept click. Deferred per task #4.
