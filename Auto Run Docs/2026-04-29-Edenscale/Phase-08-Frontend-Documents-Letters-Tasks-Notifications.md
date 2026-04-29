# Phase 08: Frontend — Documents, Letters, Tasks, Notifications

This phase finishes the page port from the prototype: Documents (with file upload via presigned URLs), Letters (LP communications with read-receipt tracking), Tasks (Kanban-style by status), and Notifications (inbox with read/archive). After this phase every link in the sidebar leads to a real, working page.

## Tasks

- [ ] Read the prototype pages and the Phase 05 backend contracts they depend on:
  - `edenscale/src/pages/DocumentsPage.tsx`, `edenscale/src/pages/LettersPage.tsx`, `edenscale/src/pages/TasksPage.tsx`, `edenscale/src/pages/NotificationsPage.tsx`
  - The `/documents/upload-init` flow and `LocalDevStorage` `POST /dev-storage/{key}` route from Phase 05
  - Existing `frontend/src/components/ui/StatusPill.tsx` and the `useApiMutation` hook for the consistent pattern

- [ ] Port the Documents page:
  - Create `frontend/src/pages/DocumentsPage.tsx` — list view with filters for `document_type`, `fund_id`, `investor_id`. Columns: title, type pill, fund, investor, file_name, size, uploaded_by, created_at
  - "Upload document" button opens `DocumentUploadDialog`:
    1. Pick file via `<input type="file">` and read `name`, `type`, `size`
    2. Call `POST /documents/upload-init` with those fields → receive `{upload_url, file_url}`
    3. `fetch(upload_url, { method: "PUT", body: file })`
    4. `POST /documents` with the metadata + `file_url`
    5. Invalidate `["documents"]`
  - Row click opens a viewer drawer with a fresh download URL from `GET /documents/{id}`
  - Replace the placeholder `/documents` route in `App.tsx`

- [ ] Port the Letters (Communications) page:
  - Create `frontend/src/pages/LettersPage.tsx` — list of communications via `useApiQuery("/communications")`. Columns: subject, type pill, fund, sent_at, recipient count, read percentage
  - "New letter" button opens `LetterComposeDialog` with subject, body (textarea, plain text for now — no rich text editor yet), fund_id picker. Save creates a draft via `POST /communications`. "Send" button posts to `POST /communications/{id}/send`
  - Detail drawer: shows recipients with per-recipient `delivered_at` / `read_at` timestamps in a small table
  - Replace the placeholder `/letters` route in `App.tsx`

- [ ] Port the Tasks page:
  - Create `frontend/src/pages/TasksPage.tsx` — Kanban-style four columns (`open`, `in_progress`, `done`, `cancelled`). Each column lists task cards via `useApiQuery("/tasks", { params: { status } })`
  - Card shows title, fund (if set), assignee avatar, due_date with red highlight when overdue
  - "New task" button opens `TaskCreateDialog` posting to `POST /tasks`
  - Card menu: mark in_progress / complete / cancel via `PATCH /tasks/{id}` and `POST /tasks/{id}/complete`
  - Filter: My tasks vs All tasks (visible only to fund_manager+admin via the role from `GET /users/me`)
  - Replace the placeholder `/tasks` route in `App.tsx`

- [ ] Port the Notifications page:
  - Create `frontend/src/pages/NotificationsPage.tsx` — chronological feed via `useApiQuery("/notifications")`. Group by date (Today / Yesterday / This Week / Earlier)
  - Each row: title, message, related entity link (e.g., "View capital call" → `/calls?focus={related_id}`), read/archive actions
  - Header actions: "Mark all read" → `POST /notifications/read-all`
  - Replace the placeholder `/notifications` route in `App.tsx`. Wire the Topbar bell badge count from this query result

- [ ] Add a shared `EmptyState.tsx` component used across all four pages:
  - Props: `icon`, `title`, `body`, optional `action` button
  - Use the `--brass-700` accent for the icon stroke and Cormorant Garamond for the title to match the design

- [ ] Type-check + visual smoke test:
  - `pnpm run lint` from `frontend/`
  - Walk through: upload a doc, send a letter, mark a task done, mark a notification read; confirm the bell badge decrements

- [ ] Run repo gates: `make lint`, `make test`, and confirm `make openapi` reports no diff
