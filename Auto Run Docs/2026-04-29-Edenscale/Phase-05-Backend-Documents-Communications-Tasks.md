# Phase 05: Backend — Documents, Communications, Tasks, Notifications, Audit Log

This phase finishes the backend by implementing the supporting tables: documents (file metadata; actual storage uses presigned URLs from a future blob provider but the API contract is in place), communications (broadcast letters/announcements with per-recipient delivery + read receipts), tasks, notifications, and the audit log. By the end of this phase, every table in `db.dbml` has a working CRUD API and the audit log captures every mutation through a small SQLAlchemy event listener.

## Tasks

- [ ] Read Phase 02-04's repositories and routers as the pattern reference; do not invent new layering

- [ ] Implement Documents:
  - `backend/app/schemas/document.py` — `DocumentCreate` (organization_id, fund_id, investor_id, document_type, title, file_name, mime_type, file_size, is_confidential), `DocumentUpdate`, `DocumentRead`, plus `DocumentUploadInit` (`file_name`, `mime_type`, `file_size`) and `DocumentUploadInitResponse` (`upload_url`, `file_url`, `expires_at`)
  - `backend/app/services/storage.py` — abstract `StoragePort` with `presign_put(key, mime_type) -> (upload_url, public_url, expires_at)` and `presign_get(key) -> url`. Provide a `LocalDevStorage` implementation that returns `http://localhost:8000/dev-storage/{key}` URLs and persists uploaded bytes under `backend/dev_storage/`. Add a tiny `POST /dev-storage/{key}` route protected by a dev-only header (skip in tests). Wire `StoragePort` selection through `settings.STORAGE_BACKEND`
  - `backend/app/repositories/document_repository.py` and `backend/app/routers/documents.py` — `POST /documents/upload-init`, `POST /documents` (records metadata after the client uploads to the presigned URL), `GET /documents`, `GET /documents/{id}` (returns a fresh presigned GET url), `PATCH /documents/{id}`, `DELETE /documents/{id}`. RBAC: confidential docs visible only to admin/fund_manager in same org and LPs whose `investor_id` matches. Mount under `/documents`

- [ ] Implement Communications + Recipients:
  - Schemas/repository/router with endpoints `GET /communications`, `GET /communications/{id}`, `POST /communications` (drafts), `PATCH /communications/{id}`, `POST /communications/{id}/send` (sets `sent_at` and creates one `communication_recipients` row per resolved recipient), `POST /communications/{id}/recipients/{recipient_id}/read` (sets `read_at`)
  - Recipient resolution helper: given a fund_id, expand to all primary investor_contacts whose investors hold an approved commitment in that fund. Allow explicit overrides via the request body `recipients: list[{ user_id?: int, investor_contact_id?: int }]`
  - Mount under `/communications`. Add nested `GET /funds/{fund_id}/communications`

- [ ] Implement Tasks:
  - Schemas/repository/router for `GET /tasks`, `GET /tasks/{id}`, `POST /tasks`, `PATCH /tasks/{id}`, `POST /tasks/{id}/complete` (sets status=done and `completed_at=now()`)
  - Default list filter: `assigned_to_user_id = current_user.id`. Query parameters `?fund_id=`, `?status=`, `?assignee=` for fund_managers/admins
  - Mount under `/tasks`. Add nested `GET /funds/{fund_id}/tasks`

- [ ] Implement Notifications:
  - Schemas/repository/router for `GET /notifications` (defaults to current user, sorted desc by `created_at`), `POST /notifications/{id}/read`, `POST /notifications/{id}/archive`, `POST /notifications/read-all`
  - Add `notification_service.notify(user_id, title, message, related_type=None, related_id=None)` and call it from key business events: capital_call sent, distribution sent, communication sent, task assigned to a different user
  - Mount under `/notifications`

- [ ] Implement the Audit Log:
  - Add `backend/app/core/audit.py` exporting `record_audit(db, user, action, entity_type, entity_id, metadata=None, request=None)` and an SQLAlchemy `after_insert` / `after_update` / `after_delete` event listener registered for the entities that matter (organizations, users, funds, commitments, capital_calls, distributions, documents, communications, tasks). The listener writes a row to `audit_logs` capturing the actor (read from a request-scoped context var set by a FastAPI middleware), the action verb, entity type/id, and a JSON-encoded diff in `metadata`
  - Add `backend/app/middleware/audit_context.py` middleware that puts the current user_id and ip_address into a `contextvars.ContextVar` for the duration of the request
  - Expose `GET /audit-logs` (admin-only) and `GET /audit-logs?entity_type=fund&entity_id=...` for tracing
  - Mount under `/audit-logs`

- [ ] Update Dashboard overview with new aggregates:
  - Surface `unread_notifications_count`, `open_tasks_count` for the current user, and `recent_communications` (5 most recent) so the Dashboard page has all the numbers it needs

- [ ] Add focused integration tests covering the new modules:
  - `backend/tests/test_documents_api.py`, `test_communications_api.py`, `test_tasks_api.py`, `test_notifications_api.py`, `test_audit_log.py` — at least one happy path and one auth/RBAC failure per module
  - For documents, use the LocalDevStorage backend in tests so the round-trip works without external dependencies

- [ ] Sync OpenAPI and run gates:
  - Run `make openapi`, `make test`, `make lint`, fix findings
  - Confirm `frontend/src/lib/schema.d.ts` exposes every new endpoint
