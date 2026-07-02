---
type: reference
title: Frontend Routing
created: 2026-04-29
tags:
  - architecture
  - frontend
  - react
related:
  - '[[System-Overview]]'
  - '[[RBAC-Model]]'
---

# Frontend Routing

The product UI is split into two Vite SPAs orchestrated by Turborepo:

- `apps/manager` mounts at `/manager` and owns manager, admin, fund-manager, and superadmin workflows.
- `apps/investor` mounts at `/investor` and owns LP-facing read-only workflows.

Both apps share generated API types/client hooks from `@edenscale/api`, Hanko auth utilities from `@edenscale/auth`, organization state and formatting utilities from `@edenscale/shared`, and NewTaven UI primitives/global CSS from `@edenscale/ui`.

## Manager Routes

| Path | Purpose |
| --- | --- |
| `/manager` | Authenticated manager dashboard / org picker |
| `/manager/profile` | Current user profile |
| `/manager/invitations/accept` | Invitation acceptance |
| `/manager/:orgSlug` | Organization overview |
| `/manager/:orgSlug/funds` | Fund management |
| `/manager/:orgSlug/investors` | Investor register and commitments |
| `/manager/:orgSlug/calls` | Capital calls |
| `/manager/:orgSlug/distributions` | Distributions |
| `/manager/:orgSlug/documents` | Documents |
| `/manager/:orgSlug/letters` | Communications |
| `/manager/:orgSlug/tasks` | Manager tasks |
| `/manager/:orgSlug/settings` | Organization settings |
| `/manager/:orgSlug/audit-log` | Audit log |
| `/manager/:orgSlug/:fundSlug` | Fund workspace |
| `/manager/superadmin/organizations` | Superadmin organization list |
| `/manager/superadmin/organizations/:organizationId` | Superadmin organization detail |

LP memberships that hit an organization-scoped manager URL are redirected to the matching `/investor/:orgSlug` URL.

## Investor Routes

| Path | Purpose |
| --- | --- |
| `/investor` | LP organization picker |
| `/investor/profile` | Current user profile |
| `/investor/invitations/accept` | Invitation acceptance |
| `/investor/:orgSlug` | Investor overview |
| `/investor/:orgSlug/funds` | Accessible funds |
| `/investor/:orgSlug/:fundSlug` | Read-only fund summary |
| `/investor/:orgSlug/calls` | Capital calls |
| `/investor/:orgSlug/distributions` | Distributions |
| `/investor/:orgSlug/documents` | Documents |
| `/investor/:orgSlug/letters` | Communications |
| `/investor/:orgSlug/notifications` | Notifications |

Non-LP memberships that hit an organization-scoped investor URL are redirected to the matching `/manager/:orgSlug` URL.

## Gateway Behavior

The Cloudflare Worker serves:

- `/` from `apps/web/dist`
- `/manager/*` from `apps/manager/dist`
- `/investor/*` from `apps/investor/dist`

Missing JS/CSS assets under the SPA mount points return the real asset 404. Only document navigations fall back to the relevant SPA `index.html`. Legacy `/app/*` URLs redirect to `/manager/*`.

## Conventions

- Generated OpenAPI types live in `packages/api/src/schema.d.ts`; do not hand-edit them.
- App-local imports use `@/*`; shared code should be imported through `@edenscale/*` package exports.
- Run `pnpm turbo run typecheck` for workspace TypeScript validation.
- Run `pnpm turbo run build --filter=manager`, `--filter=investor`, or `--filter=gateway` for targeted frontend builds.
