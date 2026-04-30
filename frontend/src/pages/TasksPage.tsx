import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useQueryClient } from "@tanstack/react-query"
import { CalendarDays, Loader2, MoreHorizontal } from "lucide-react"
import { toast } from "sonner"

import { TaskCreateDialog } from "@/components/tasks/TaskCreateDialog"
import { PageHero } from "@/components/layout/PageHero"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Eyebrow } from "@/components/ui/eyebrow"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { components } from "@/lib/schema"

type TaskStatus = components["schemas"]["TaskStatus"]
type TaskRead = components["schemas"]["TaskRead"]

const LANES: Array<{ id: TaskStatus; label: string }> = [
  { id: "open", label: "Open" },
  { id: "in_progress", label: "In progress" },
  { id: "done", label: "Done" },
  { id: "cancelled", label: "Cancelled" },
]

type AssigneeFilter = "mine" | "all"

function deriveInitials(first?: string | null, last?: string | null, email?: string | null) {
  const f = (first ?? "").trim()
  const l = (last ?? "").trim()
  if (f && l) return (f[0] + l[0]).toUpperCase()
  if (f.length >= 2) return f.slice(0, 2).toUpperCase()
  const local = (email ?? "").split("@")[0] ?? ""
  const parts = local.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (local.slice(0, 2) || "ES").toUpperCase()
}

function isOverdue(dueDate: string | null, status: TaskStatus) {
  if (!dueDate) return false
  if (status === "done" || status === "cancelled") return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(dueDate)
  return due.getTime() < today.getTime()
}

export default function TasksPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [assigneeFilter, setAssigneeFilter] = useState<AssigneeFilter>("mine")

  const queryClient = useQueryClient()
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const role = meQuery.data?.role
  const canManage = role === "admin" || role === "fund_manager"
  const effectiveFilter: AssigneeFilter = canManage ? assigneeFilter : "mine"

  const tasksQuery = useApiQuery("/tasks", {
    params: {
      query: {
        ...(effectiveFilter === "mine" && meQuery.data
          ? { assignee: meQuery.data.id }
          : {}),
        limit: 200,
      },
    },
  })
  const fundsQuery = useApiQuery("/funds")
  const usersQuery = useApiQuery("/users", undefined, { enabled: canManage })

  const tasks = useMemo(() => tasksQuery.data ?? [], [tasksQuery.data])

  const fundNameById = useMemo(() => {
    const map = new Map<number, string>()
    for (const f of fundsQuery.data ?? []) map.set(f.id, f.name)
    return map
  }, [fundsQuery.data])

  const userById = useMemo(() => {
    const map = new Map<
      number,
      { name: string; email: string; first: string | null; last: string | null }
    >()
    const list = usersQuery.data ?? (meQuery.data ? [meQuery.data] : [])
    for (const u of list) {
      const name = `${u.first_name} ${u.last_name}`.trim() || u.email
      map.set(u.id, {
        name,
        email: u.email,
        first: u.first_name,
        last: u.last_name,
      })
    }
    return map
  }, [usersQuery.data, meQuery.data])

  const lanes = useMemo(() => {
    return LANES.map((lane) => ({
      ...lane,
      items: tasks.filter((t) => t.status === lane.id),
    }))
  }, [tasks])

  const updateTask = useApiMutation("patch", "/tasks/{task_id}")
  const completeTask = useApiMutation("post", "/tasks/{task_id}/complete")

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["/tasks"] })
    queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
  }

  async function handleSetStatus(task: TaskRead, next: TaskStatus) {
    try {
      if (next === "done") {
        await completeTask.mutateAsync({
          params: { path: { task_id: task.id } },
        })
        toast.success("Task completed")
      } else {
        await updateTask.mutateAsync({
          params: { path: { task_id: task.id } },
          body: { status: next },
        })
        toast.success(
          next === "in_progress"
            ? "Marked in progress"
            : next === "open"
              ? "Reopened"
              : "Task cancelled",
        )
      }
      invalidate()
    } catch {
      // useApiMutation surfaces a toast already
    }
  }

  return (
    <>
      <Helmet>
        <title>{`Tasks · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Workflow"
        title="Tasks across the firm."
        description="Open items assigned across investor relations, compliance, and finance."
        actions={
          canManage ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setCreateOpen(true)}
            >
              New task
            </Button>
          ) : null
        }
      />

      <div className="px-8 pb-16">
        {canManage && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Eyebrow>View</Eyebrow>
            <div className="inline-flex items-center border border-[color:var(--border-hairline)]">
              {(["mine", "all"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setAssigneeFilter(value)}
                  className={cn(
                    "px-3.5 py-1.5 font-sans text-[12px] tracking-tight transition-colors",
                    assigneeFilter === value
                      ? "bg-conifer-700 text-parchment-50"
                      : "bg-surface text-ink-700 hover:bg-parchment-200",
                  )}
                >
                  {value === "mine" ? "My tasks" : "All tasks"}
                </button>
              ))}
            </div>
            <span className="ml-auto font-sans text-[12px] text-ink-500">
              {tasks.length} task{tasks.length === 1 ? "" : "s"}
            </span>
          </div>
        )}

        {tasksQuery.isLoading ? (
          <div className="flex min-h-[320px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            {lanes.map((lane) => (
              <Card key={lane.id} className="flex flex-col">
                <div className="flex items-center justify-between px-6 pt-6 md:px-7 md:pt-7">
                  <Eyebrow>{lane.label}</Eyebrow>
                  <span className="font-sans text-[12px] text-ink-500">
                    {lane.items.length}
                  </span>
                </div>
                <CardSection className="flex flex-1 flex-col gap-3 pt-4">
                  {lane.items.length === 0 && (
                    <p className="font-sans text-[13px] text-ink-500">
                      Nothing here.
                    </p>
                  )}
                  {lane.items.map((task) => {
                    const fundName =
                      task.fund_id !== null
                        ? (fundNameById.get(task.fund_id) ??
                          `Fund #${task.fund_id}`)
                        : null
                    const assignee =
                      task.assigned_to_user_id !== null
                        ? userById.get(task.assigned_to_user_id)
                        : null
                    const overdue = isOverdue(task.due_date, task.status)
                    return (
                      <article
                        key={task.id}
                        className="flex flex-col gap-3 border border-[color:var(--border-hairline)] bg-page p-4 transition-colors hover:border-[color:var(--border-default)]"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-sans text-[14px] leading-[1.4] text-ink-900">
                            {task.title}
                          </span>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              aria-label="Task actions"
                              className="-mr-1 -mt-1 inline-flex size-7 shrink-0 items-center justify-center text-ink-500 hover:text-ink-900 focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2"
                            >
                              <MoreHorizontal
                                strokeWidth={1.5}
                                className="size-4"
                              />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-44">
                              {task.status !== "in_progress" &&
                                task.status !== "done" &&
                                task.status !== "cancelled" && (
                                  <DropdownMenuItem
                                    onSelect={() =>
                                      handleSetStatus(task, "in_progress")
                                    }
                                  >
                                    Mark in progress
                                  </DropdownMenuItem>
                                )}
                              {task.status === "in_progress" && (
                                <DropdownMenuItem
                                  onSelect={() => handleSetStatus(task, "open")}
                                >
                                  Move to open
                                </DropdownMenuItem>
                              )}
                              {task.status !== "done" && (
                                <DropdownMenuItem
                                  onSelect={() => handleSetStatus(task, "done")}
                                >
                                  Mark complete
                                </DropdownMenuItem>
                              )}
                              {task.status !== "cancelled" &&
                                task.status !== "done" && (
                                  <DropdownMenuItem
                                    onSelect={() =>
                                      handleSetStatus(task, "cancelled")
                                    }
                                  >
                                    Cancel task
                                  </DropdownMenuItem>
                                )}
                              {(task.status === "done" ||
                                task.status === "cancelled") && (
                                <DropdownMenuItem
                                  onSelect={() => handleSetStatus(task, "open")}
                                >
                                  Reopen
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>

                        {(fundName || task.due_date) && (
                          <div className="flex flex-wrap items-center gap-2 font-sans text-[11px] text-ink-500">
                            {fundName && <span>{fundName}</span>}
                            {fundName && task.due_date && (
                              <span className="size-1 rounded-full bg-ink-300" />
                            )}
                            {task.due_date && (
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1",
                                  overdue && "text-[color:var(--status-negative)]",
                                )}
                              >
                                <CalendarDays
                                  strokeWidth={1.5}
                                  className="size-3"
                                />
                                {overdue ? "Overdue · " : "Due "}
                                {formatDate(task.due_date)}
                              </span>
                            )}
                          </div>
                        )}

                        <div className="flex items-center justify-between border-t border-[color:var(--border-hairline)] pt-3">
                          {assignee ? (
                            <div className="flex items-center gap-2">
                              <span className="inline-flex size-6 items-center justify-center bg-conifer-700 font-display text-[10px] font-medium text-parchment-50">
                                {deriveInitials(
                                  assignee.first,
                                  assignee.last,
                                  assignee.email,
                                )}
                              </span>
                              <span className="font-sans text-[11px] text-ink-700">
                                {assignee.name}
                              </span>
                            </div>
                          ) : (
                            <span className="font-sans text-[11px] text-ink-500">
                              Unassigned
                            </span>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </CardSection>
              </Card>
            ))}
          </div>
        )}
      </div>

      <TaskCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </>
  )
}
