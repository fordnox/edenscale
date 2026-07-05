---
title: Account, tasks and notifications
description: The investor's self-service surface — profile, notifications, assigned tasks, invitations, and their own audit trail.
---

These endpoints are user-scoped rather than portfolio-scoped; most of them work without an `X-Organization-Id` header.

## Profile

- `GET /users/me` — the investor's own user record.
- `PATCH /users/me` — update their own profile (self-editable fields only; roles and other users are untouchable — the org roster at `GET /users` is manager-only).
- `GET /users/me/memberships` — all of the user's memberships across organizations; the investor portal uses this to build the org switcher (only `lp` memberships are shown there).

## Notifications

Notifications are delivered in-app (and by email through the event bus) for events like capital calls, distributions, uploaded documents, commitment status changes, task assignment, and communications. All endpoints operate on the caller's own rows only:

| Endpoint | Behavior |
| --- | --- |
| `GET /notifications` | List own notifications, filterable by status (`unread` / `read` / `archived`) |
| `POST /notifications/read-all` | Mark all own notifications read; returns the count |
| `POST /notifications/{id}/read` | Mark one read (`403` if it belongs to someone else) |
| `POST /notifications/{id}/archive` | Archive one (same ownership guard) |

## Tasks

An LP only ever sees tasks **assigned to them** — `GET /tasks` forcibly overrides the `assignee` filter to their own user id. They cannot create tasks or edit task metadata, but `POST /tasks/{id}/complete` lets them mark an assigned task done. See the [Tasks guide](/docs/guides/tasks/) for the full model.

## Invitations

- `GET /invitations/pending-for-me` — pending invitations addressed to the caller's email (the portal shows these in a banner).
- `POST /invitations/accept` — accept one. This validates the email match, creates or updates the membership with the invited role, and links unclaimed investor-contact rows by email — the step that actually connects a new LP to their investor entity. Expired, revoked, already-accepted, or mismatched invitations are rejected.

Issuing, revoking, and resending invitations are admin-only.

## Audit log

`GET /audit-logs` is available to LPs, but the `user_id` filter is forced to their own id — an investor sees only the events **they themselves caused** in the active organization, never other users' activity.
