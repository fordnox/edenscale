# Phase 08: Frontend — Documents, Letters, Tasks, Notifications

This phase finishes the page port from the prototype: Documents (with file upload via presigned URLs), Letters (LP communications with read-receipt tracking), Tasks (Kanban-style by status), and Notifications (inbox with read/archive). After this phase every link in the sidebar leads to a real, working page.

## Tasks

- [x] Read the prototype pages and the Phase 05 backend contracts they depend on:
  - `edenscale/src/pages/DocumentsPage.tsx`, `edenscale/src/pages/LettersPage.tsx`, `edenscale/src/pages/TasksPage.tsx`, `edenscale/src/pages/NotificationsPage.tsx`
  - The `/documents/upload-init` flow and `LocalDevStorage` `POST /dev-storage/{key}` route from Phase 05
  - Existing `frontend/src/components/ui/StatusPill.tsx` and the `useApiMutation` hook for the consistent pattern

  Notes after reading:
  - **Documents prototype** uses filter chips (`all` + 6 `DocumentType`s), a `DataTable` with columns `Document` (title + file_name + confidential icon), `Linked to`, `Type`, `Size`, `Uploaded` (date + uploader), and a per-row Download button. "Upload document" CTA opens a dialog. Backend `DocumentRead` already returns `download_url` (presigned), `file_size`, `file_url`, `mime_type`, `is_confidential`, `uploaded_by_user_id`. Backend list filters: `organization_id`, `fund_id`, `investor_id`, `document_type`, `skip`, `limit`. Backend exposes `POST /documents/upload-init` returning `{upload_url, file_url, expires_at}` and `POST /documents` for the metadata record. The dev-storage PUT route requires header `x-dev-storage-token` (so the upload-init flow needs to include it for local backend; production presigned S3 URLs would not).
  - **Letters prototype** is editorial/featured-letter centric; the actual phase task asks for a flatter list view with subject/type/fund/sent_at/recipients/read% and a compose dialog using `POST /communications` + `POST /communications/{id}/send`, plus a per-recipient timestamps drawer.
  - **Tasks prototype** has 3 lanes (open/in_progress/done), but the phase task adds a 4th `cancelled` lane and per-card menu actions. Filter "My tasks vs All tasks" depends on caller role from `GET /users/me`.
  - **Notifications prototype** groups by unread/earlier; phase task asks for date grouping (Today / Yesterday / This Week / Earlier), per-row read+archive actions, and a "Mark all read" → `POST /notifications/read-all`. Topbar bell badge count is wired from this query.
  - **Existing pattern**: `StatusPill` already supports `kind="task"` and `kind="notification"`. `useApiQuery`/`useApiMutation` are typed via the generated OpenAPI client and integrate with `client.GET/POST/PATCH/...`. Mutations should `queryClient.invalidateQueries({ queryKey: [path] })` to refresh.

- [x] Port the Documents page:
  - Create `frontend/src/pages/DocumentsPage.tsx` — list view with filters for `document_type`, `fund_id`, `investor_id`. Columns: title, type pill, fund, investor, file_name, size, uploaded_by, created_at
  - "Upload document" button opens `DocumentUploadDialog`:
    1. Pick file via `<input type="file">` and read `name`, `type`, `size`
    2. Call `POST /documents/upload-init` with those fields → receive `{upload_url, file_url}`
    3. `fetch(upload_url, { method: "PUT", body: file })`
    4. `POST /documents` with the metadata + `file_url`
    5. Invalidate `["documents"]`
  - Row click opens a viewer drawer with a fresh download URL from `GET /documents/{id}`
  - Replace the placeholder `/documents` route in `App.tsx`

  Notes:
  - `DocumentsPage.tsx` ports the prototype filter chips for `document_type` and adds two `Select` filters for `fund_id` / `investor_id`. The list query is `useApiQuery("/documents", { params: { query: { document_type, fund_id, investor_id } } })` so backend filtering does the work.
  - `DocumentRead` doesn't include fund/investor names, so the page joins client-side via separate `useApiQuery("/funds")` and `useApiQuery("/investors")` lookups, falling back to `Fund #N` if the user lacks visibility.
  - `DocumentUploadDialog.tsx` runs the four-step presigned-URL flow. For local dev (`/dev-storage/` URLs) it attaches the `x-dev-storage-token` header from a new `VITE_DEV_STORAGE_TOKEN` (default `dev-storage`). Production presigned S3 URLs skip the header.
  - Row click opens a `Sheet` rendering `DocumentDetail.tsx`, which calls `GET /documents/{id}` for a fresh `download_url` and exposes a "Download" link that opens in a new tab. The dialog also lets the user link the doc to a fund/investor or upload as firm-wide, plus a Confidential checkbox (default true).
  - `App.tsx` swaps the `ComingSoon` placeholder for `<DocumentsPage />`. Lint (`pnpm run lint`) passes.

- [x] Port the Letters (Communications) page:
  - Create `frontend/src/pages/LettersPage.tsx` — list of communications via `useApiQuery("/communications")`. Columns: subject, type pill, fund, sent_at, recipient count, read percentage
  - "New letter" button opens `LetterComposeDialog` with subject, body (textarea, plain text for now — no rich text editor yet), fund_id picker. Save creates a draft via `POST /communications`. "Send" button posts to `POST /communications/{id}/send`
  - Detail drawer: shows recipients with per-recipient `delivered_at` / `read_at` timestamps in a small table
  - Replace the placeholder `/letters` route in `App.tsx`

  Notes:
  - `LettersPage.tsx` lists communications with two filters (`type` enum, `fund_id`). The list query uses `useApiQuery("/communications", { params: { query: { type, fund_id } } })`; columns are subject (with envelope icon), type Badge (announcement/info, message/active, notification/warning), fund name (joined client-side from `/funds`, falling back to `Fund #N`), sent_at, recipient count, and a percentage + ProgressBar for read rate. Drafts show "—" for sent_at.
  - `LetterComposeDialog.tsx` posts the draft via `POST /communications`, then optionally chains `POST /communications/{id}/send` when the user clicks "Send now". Both buttons share submit guards and surface their loading state independently.
  - `LetterDetail.tsx` opens in a Sheet, hydrates with `GET /communications/{id}`, and joins `/users` to enrich `user_id` recipients with names + email; `investor_contact_id` rows fall back to `Contact #N`. Read receipts render with date+time via `formatDate(..., { hour, minute })`. The drawer also exposes a "Send now" CTA when the letter is still a draft.
  - `App.tsx` swaps the `ComingSoon` placeholder for `<LettersPage />`. `pnpm run lint` (`tsc --noEmit`) passes.

- [x] Port the Tasks page:
  - Create `frontend/src/pages/TasksPage.tsx` — Kanban-style four columns (`open`, `in_progress`, `done`, `cancelled`). Each column lists task cards via `useApiQuery("/tasks", { params: { status } })`
  - Card shows title, fund (if set), assignee avatar, due_date with red highlight when overdue
  - "New task" button opens `TaskCreateDialog` posting to `POST /tasks`
  - Card menu: mark in_progress / complete / cancel via `PATCH /tasks/{id}` and `POST /tasks/{id}/complete`
  - Filter: My tasks vs All tasks (visible only to fund_manager+admin via the role from `GET /users/me`)
  - Replace the placeholder `/tasks` route in `App.tsx`

  Notes:
  - `TasksPage.tsx` fetches `/tasks` once with `limit: 200` and partitions client-side into the four lanes (`open`, `in_progress`, `done`, `cancelled`); going one-shot avoids four parallel queries that would each duplicate the role-based assignee filter on the backend. Loading state renders a single spinner above the grid.
  - The "My tasks vs All tasks" segmented toggle is rendered only when `useApiQuery("/users/me").data.role` is `admin` or `fund_manager`; for LPs the page silently hard-codes the `mine` view (and the backend already enforces this). When `mine` is active the query passes `assignee={me.id}`; switching to `all` drops the param so admins/fund managers see every task they can manage.
  - Card cluster: title + per-card `DropdownMenu` with the status transitions called for in the spec — `Mark in progress`, `Move to open`, `Mark complete`, `Cancel task`, plus a `Reopen` shortcut for completed/cancelled rows. `Mark complete` posts to `/tasks/{id}/complete` (no body — the schema declares `requestBody?: never`, so the call omits `body` rather than passing `null` like the letters send endpoint does); the other transitions go through `PATCH /tasks/{id}`. Each mutation invalidates `["/tasks"]` and `["/dashboard"]`.
  - Fund names are joined client-side from `/funds` (falling back to `Fund #N`); assignee chips use shared `deriveInitials(...)` logic and the conifer-700 swatch from the topbar, with the fallback "Unassigned". The users lookup pulls `/users` only when `canManage` is true, otherwise it falls back to the current user record so LPs still see their own initials. Due dates show a `CalendarDays` icon and turn `--status-negative` (the existing red-clay token) when the date is in the past _and_ the task is not yet `done`/`cancelled`.
  - `TaskCreateDialog.tsx` matches the Documents/Letters dialog patterns (Dialog + form + Loader2 spinner + sonner toasts). It posts a `TaskCreate` body — title, optional description, fund, assignee, due date, and explicit `status: "open"` to satisfy the OpenAPI default. The "New task" button is hidden for LPs since the backend gates `POST /tasks` to admin/fund_manager.
  - `App.tsx` swaps the `ComingSoon` placeholder for `<TasksPage />`. `pnpm run lint` (`tsc --noEmit`) passes.

- [x] Port the Notifications page:
  - Create `frontend/src/pages/NotificationsPage.tsx` — chronological feed via `useApiQuery("/notifications")`. Group by date (Today / Yesterday / This Week / Earlier)
  - Each row: title, message, related entity link (e.g., "View capital call" → `/calls?focus={related_id}`), read/archive actions
  - Header actions: "Mark all read" → `POST /notifications/read-all`
  - Replace the placeholder `/notifications` route in `App.tsx`. Wire the Topbar bell badge count from this query result

  Notes:
  - `NotificationsPage.tsx` fetches `/notifications` once with `limit: 200` and partitions client-side into the four date buckets (Today / Yesterday / This week / Earlier). Archived notifications are hidden from the inbox; only `unread` and `read` rows show. Day-bucketing uses the local-time start of each day so a notification created late at night still shows under "Today" until midnight.
  - Each row shows a brass-500 dot when unread (ink-300 once read, plus 80% opacity), the title (semibold when unread, medium otherwise), the message body, and a metadata strip with `titleCase(related_type)`, `formatDate(created_at)`, and a context-specific link when both `related_type` and `related_id` are set. The `relatedLink(...)` helper maps the backend's free-form `related_type` strings (`capital_call`, `distribution`, `investor`, `document`, `communication`/`letter`, `task`, `fund`) to in-app routes — most use `/{section}?focus={id}` per the phase example, while `fund` jumps to the existing `/funds/{id}` detail. Unrecognized types render with no link rather than a broken URL.
  - Per-row actions are ghost buttons: a `CheckCheck` icon to mark read (only rendered when status is `unread`) calls `POST /notifications/{id}/read`, and an `Archive` icon calls `POST /notifications/{id}/archive`. The header CTA is "Mark all as read" → `POST /notifications/read-all`, disabled when `unreadCount === 0` or the mutation is pending. Each mutation invalidates `["/notifications"]` and `["/dashboard/overview"]` so the dashboard counter and bell badge stay in sync. `useApiMutation` already shows a sonner toast on error.
  - Topbar bell badge: `Topbar.tsx` no longer reads `overview.unread_notifications_count`; instead it shares the same `useApiQuery("/notifications", { params: { query: { limit: 200 } } })` and counts `n.status === "unread"` client-side. After a mark-read mutation invalidates `["/notifications"]`, the badge decrements automatically without a separate dashboard refetch. Using a 60s `staleTime` keeps the request cheap.
  - `App.tsx` swaps the `ComingSoon` placeholder for `<NotificationsPage />` and drops the now-unused `ComingSoon` import. `pnpm run lint` (`tsc --noEmit`) passes.

- [x] Add a shared `EmptyState.tsx` component used across all four pages:
  - Props: `icon`, `title`, `body`, optional `action` button
  - Use the `--brass-700` accent for the icon stroke and Cormorant Garamond for the title to match the design

  Notes:
  - `frontend/src/components/ui/EmptyState.tsx` exposes `{ icon, title, body, action, className }`. The icon slot wraps any node (typically a Lucide icon) and forces `size-8` + `stroke-[1.25]` via `[&_svg]:` arbitrary selectors so callers can pass `<FileText strokeWidth={1.25} />` without separately sizing it. The wrapper applies `text-[color:var(--brass-700)]`, so any SVG using `currentColor` (Lucide default) inherits the aged-brass stroke. The title renders `font-display` (Cormorant Garamond) at 28px / 500 weight with `tracking-[-0.015em]` to mirror the `.es-display` token. Body copy uses the page's standard 14px ink-700 paragraph style and `max-w-md`. The action slot accepts arbitrary nodes (not strictly a button) so a row of buttons or a link could also be passed.
  - The component is centered (`items-center`, `text-center`) — chosen over the prior left-aligned inline copy because an icon-led empty state reads best symmetrically. Existing inline empty states on Documents and Letters were swapped over: `DocumentsPage` uses `FileText`, `LettersPage` uses `Mail`, `NotificationsPage` uses `BellOff`, and `TasksPage` adds a top-level `ClipboardList` empty state when *all* lanes are empty (per-lane "Nothing here." copy is kept for partially-empty boards since the EmptyState would crowd a narrow Kanban column). The Tasks empty state branches on `effectiveFilter` so an LP/manager viewing "My tasks" sees "No tasks assigned to you" and only managers see the "New task" action.
  - `pnpm run lint` (`tsc --noEmit`) passes.

- [ ] Type-check + visual smoke test:
  - `pnpm run lint` from `frontend/`
  - Walk through: upload a doc, send a letter, mark a task done, mark a notification read; confirm the bell badge decrements

- [ ] Run repo gates: `make lint`, `make test`, and confirm `make openapi` reports no diff
