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
