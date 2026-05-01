---
type: note
title: Superadmin Console Follow-ups
created: 2026-05-01
tags:
  - superadmin
  - frontend
  - phase-06
  - followups
related:
  - '[[Phase-06-Superadmin-Frontend]]'
  - '[[active-org-audit]]'
---

# Superadmin Console — UX & Implementation Follow-ups

Notes captured during Phase 06 implementation. Items below were intentionally
deferred so the phase could ship without expanding scope into backend or
contract changes.

## Editing org name / legal name from the superadmin detail page

The Phase 06 spec calls for *"edit-on-click name/legal_name"* on
`SuperadminOrganizationDetailPage`. The shipped page is **read-only** for
firm metadata.

**Why deferred:** `PATCH /organizations/{organization_id}` is gated by
`require_membership_roles(UserRole.admin)` and additionally checks
`membership.organization_id == organization_id`. A superadmin viewing org A
while their active membership is in org B would 403, and a superadmin with
no membership at all would 400 ("X-Organization-Id required").

**How to apply:** Either (a) add `UserRole.superadmin` to the allow-list and
drop the org-id equality check for that role, or (b) introduce a dedicated
`PATCH /superadmin/organizations/{organization_id}` route mirroring
`OrganizationUpdate`. Option (b) is cleaner because the existing route's
docstring deliberately fences itself to a single org's admin.

## Sidebar tagline for superadmins without an active membership

`Sidebar.tsx` derives the user's role tagline from
`activeMembership?.role` (via `useNavItems`). For a pure superadmin (no
memberships), the role is `null` and the fallback string is "Manager view",
which is misleading.

**Suggested fix:** Add a `superadmin` key to `ROLE_TAGLINES` and prefer the
global `me.role` over the active membership when the user is a superadmin
without an active org context.

## Promote-existing-user list is scoped to the current org's members

`AssignAdminDialog` accepts an `existingUsers` prop fed by the org's
members endpoint (so superadmins can promote a fund manager to admin). It
deliberately does **not** call `GET /users`, because that endpoint is
tenant-scoped via the `X-Organization-Id` middleware header and would only
show users from whatever org the superadmin had previously selected — not
the org being managed.

**Future enhancement:** Add a superadmin-only `GET /superadmin/users` (or
extend `/users` to allow a `?organization_id=` query for superadmins) so
the dialog can offer cross-org user selection.

## Active-org context conflict during superadmin browsing

When a superadmin clicks into `/superadmin/organizations/123` while their
active org context is `7`, every tenant-scoped query in the page (including
`GET /organizations/{organization_id}`) still attaches
`X-Organization-Id: 7`. `GET /organizations/{id}` is *not* tenant-scoped on
the backend, so the read works, but other future queries on this page may
not.

**Suggested fix:** Allow per-call header overrides in `lib/api.ts`'s
middleware, or expose an `act-as-org` helper for superadmin pages.

## Smoke test note

Browser smoke testing was skipped — there is no automated frontend test
harness in this repo, and a live Hanko sign-in / superadmin promotion is
out of scope for the autonomous run. `pnpm run lint` (tsc --noEmit) passes,
and `make lint` passes for the whole repo.
