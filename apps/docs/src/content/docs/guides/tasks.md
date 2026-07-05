---
title: Tasks
description: How tasks work — data model, assignment, notifications, and role-based visibility.
---

Tasks are lightweight to-do items, optionally tied to a fund and optionally assigned to a user. Assignment is always manual and explicit — there is no automatic assignment logic; a task gets an assignee only when someone sets `assigned_to_user_id` at creation or via an update.

## Data model

Defined in `apps/backend/app/models/task.py`. A task has:

| Field | Notes |
| --- | --- |
| `fund_id` | Optional. Links the task to a fund (and therefore an organization). |
| `assigned_to_user_id` | Optional. The user responsible for the task. |
| `created_by_user_id` | Set automatically from the authenticated caller. |
| `title` / `description` | Title is required (1–255 chars); description is free text. |
| `status` | `open` → `in_progress` → `done` / `cancelled` (`TaskStatus` enum). |
| `due_date` | Optional date. |
| `completed_at` | Stamped automatically when the task transitions to `done`, cleared if it moves back to a non-done status. |

## When tasks are assigned

Assignment happens in exactly two places (`apps/backend/app/routers/tasks.py`):

1. **On creation** (`POST /tasks`) — only admins, fund managers, and superadmins can create tasks. The creator may pass `assigned_to_user_id` in the request body. If it is set and the assignee is not the creator, a `TASK_ASSIGNED` notification is published to the assignee via `notify_task_assigned` (email/in-app through the event bus).
2. **On reassignment** (`PATCH /tasks/{id}`) — anyone who can manage the task can change `assigned_to_user_id`. A notification is sent only when the assignee actually *changed*, is non-null, and is not the person making the edit.

Notifications are branded with the organization the task's fund belongs to; a task with no fund produces an unbranded notification.

## Visibility and permissions

Access rules live in `apps/backend/app/repositories/task_repository.py` and are role-driven:

### Admin / fund manager / superadmin

- See tasks belonging to any fund in their organization, plus anything assigned to or created by them.
- Convenience default: listing tasks with no filters at all returns only *their own* assigned tasks.
- Can edit and reassign a task if they created it or it belongs to a fund in their organization. Org-wide tasks with no fund can only be edited by their creator.

### LPs / non-privileged members

- Only ever see tasks assigned to them — the `assignee` query parameter is forcibly overridden to their own user id.
- Cannot create tasks or edit task metadata.
- **Can** complete a task assigned to them.

### Completing a task

`POST /tasks/{id}/complete` is allowed for anyone who can manage the task, *plus* the assignee — so an LP can mark their own task done without being able to edit or reassign it. Completing an already-`done` task is a no-op; completing a `cancelled` task returns `409 Conflict`.

## Edge cases worth knowing

- A task with no fund and no assignee is visible only to its creator.
- Attaching a fund (at creation or update) is validated against the caller's organization, so tasks cannot be hung on another organization's fund (404 if the fund doesn't exist, 403 if it belongs to a different org).
