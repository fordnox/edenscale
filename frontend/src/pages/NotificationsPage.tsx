import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { useQueryClient } from "@tanstack/react-query"
import { Archive, BellOff, CheckCheck, Loader2 } from "lucide-react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { PageHero } from "@/components/layout/PageHero"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Eyebrow } from "@/components/ui/eyebrow"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatDate, titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { components } from "@/lib/schema"

type NotificationRead = components["schemas"]["NotificationRead"]

type GroupId = "today" | "yesterday" | "this_week" | "earlier"

const GROUP_LABELS: Record<GroupId, string> = {
  today: "Today",
  yesterday: "Yesterday",
  this_week: "This week",
  earlier: "Earlier",
}

const GROUP_ORDER: GroupId[] = ["today", "yesterday", "this_week", "earlier"]

function startOfDay(d: Date) {
  const next = new Date(d)
  next.setHours(0, 0, 0, 0)
  return next
}

function groupForDate(value: string | null, today: Date): GroupId {
  if (!value) return "earlier"
  const created = startOfDay(new Date(value))
  const todayStart = startOfDay(today)
  const diffDays = Math.round(
    (todayStart.getTime() - created.getTime()) / (1000 * 60 * 60 * 24),
  )
  if (diffDays <= 0) return "today"
  if (diffDays === 1) return "yesterday"
  if (diffDays <= 7) return "this_week"
  return "earlier"
}

function relatedLink(
  related_type: string | null,
  related_id: number | null,
): { to: string; label: string } | null {
  if (!related_type || related_id === null) return null
  const focus = `?focus=${related_id}`
  switch (related_type) {
    case "capital_call":
      return { to: `/calls${focus}`, label: "View capital call" }
    case "distribution":
      return { to: `/distributions${focus}`, label: "View distribution" }
    case "investor":
      return { to: `/investors${focus}`, label: "View investor" }
    case "document":
      return { to: `/documents${focus}`, label: "View document" }
    case "communication":
    case "letter":
      return { to: `/letters${focus}`, label: "View letter" }
    case "task":
      return { to: `/tasks${focus}`, label: "View task" }
    case "fund":
      return { to: `/funds/${related_id}`, label: "View fund" }
    default:
      return null
  }
}

export default function NotificationsPage() {
  const queryClient = useQueryClient()

  const notificationsQuery = useApiQuery("/notifications", {
    params: { query: { limit: 200 } },
  })

  const notifications = useMemo(
    () => notificationsQuery.data ?? [],
    [notificationsQuery.data],
  )

  const inbox = useMemo(
    () => notifications.filter((n) => n.status !== "archived"),
    [notifications],
  )
  const unreadCount = useMemo(
    () => inbox.filter((n) => n.status === "unread").length,
    [inbox],
  )

  const grouped = useMemo(() => {
    const today = new Date()
    const buckets: Record<GroupId, NotificationRead[]> = {
      today: [],
      yesterday: [],
      this_week: [],
      earlier: [],
    }
    for (const n of inbox) {
      buckets[groupForDate(n.created_at, today)].push(n)
    }
    return buckets
  }, [inbox])

  const markRead = useApiMutation(
    "post",
    "/notifications/{notification_id}/read",
  )
  const archive = useApiMutation(
    "post",
    "/notifications/{notification_id}/archive",
  )
  const markAllRead = useApiMutation("post", "/notifications/read-all")

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["/notifications"] })
    queryClient.invalidateQueries({ queryKey: ["/dashboard/overview"] })
  }

  async function handleMarkRead(notificationId: number) {
    try {
      await markRead.mutateAsync({
        params: { path: { notification_id: notificationId } },
      })
      invalidate()
    } catch {
      // useApiMutation surfaces a toast already
    }
  }

  async function handleArchive(notificationId: number) {
    try {
      await archive.mutateAsync({
        params: { path: { notification_id: notificationId } },
      })
      toast.success("Notification archived")
      invalidate()
    } catch {
      // useApiMutation surfaces a toast already
    }
  }

  async function handleMarkAllRead() {
    if (unreadCount === 0) return
    try {
      const result = await markAllRead.mutateAsync({})
      toast.success(
        result.updated === 1
          ? "Marked 1 notification as read"
          : `Marked ${result.updated} notifications as read`,
      )
      invalidate()
    } catch {
      // useApiMutation surfaces a toast already
    }
  }

  return (
    <>
      <Helmet>
        <title>{`Notifications · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Inbox"
        title="What is new."
        description="Capital activity, document releases, and investor correspondence."
        actions={
          <Button
            variant="secondary"
            size="sm"
            disabled={unreadCount === 0 || markAllRead.isPending}
            onClick={handleMarkAllRead}
          >
            {markAllRead.isPending ? (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            ) : (
              <CheckCheck strokeWidth={1.5} className="size-4" />
            )}
            Mark all as read
          </Button>
        }
      />

      <div className="px-8 pb-16">
        {notificationsQuery.isLoading ? (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : inbox.length === 0 ? (
          <Card>
            <EmptyState
              icon={<BellOff strokeWidth={1.25} />}
              title="All caught up"
              body="There are no notifications in your inbox. Capital activity, document releases, and investor correspondence will appear here."
            />
          </Card>
        ) : (
          <div className="flex flex-col gap-10">
            {GROUP_ORDER.map((groupId) => {
              const items = grouped[groupId]
              if (items.length === 0) return null
              return (
                <section key={groupId}>
                  <div className="mb-4 flex items-end justify-between">
                    <Eyebrow>{GROUP_LABELS[groupId]}</Eyebrow>
                    <span className="font-sans text-[12px] text-ink-500">
                      {items.length}
                    </span>
                  </div>
                  <Card>
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {items.map((n) => {
                        const link = relatedLink(n.related_type, n.related_id)
                        const isUnread = n.status === "unread"
                        return (
                          <li
                            key={n.id}
                            className={cn(
                              "flex items-start gap-4 px-6 py-5 md:px-8",
                              !isUnread && "opacity-80",
                            )}
                          >
                            <span
                              aria-hidden
                              className={cn(
                                "mt-2 inline-block size-2 shrink-0 rounded-full",
                                isUnread ? "bg-brass-500" : "bg-ink-300",
                              )}
                            />
                            <div className="flex flex-1 flex-col gap-1.5">
                              <span
                                className={cn(
                                  "font-sans text-[15px] tracking-[-0.005em] text-ink-900",
                                  isUnread ? "font-semibold" : "font-medium",
                                )}
                              >
                                {n.title}
                              </span>
                              <p className="font-sans text-[14px] leading-[1.55] text-ink-700">
                                {n.message}
                              </p>
                              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1.5 font-sans text-[11px] text-ink-500">
                                {n.related_type && (
                                  <span>{titleCase(n.related_type)}</span>
                                )}
                                {n.related_type && n.created_at && (
                                  <span className="size-1 rounded-full bg-ink-300" />
                                )}
                                {n.created_at && (
                                  <span>{formatDate(n.created_at)}</span>
                                )}
                                {link && (
                                  <>
                                    <span className="size-1 rounded-full bg-ink-300" />
                                    <Link
                                      to={link.to}
                                      className="text-conifer-700 underline-offset-4 hover:underline focus-visible:underline focus-visible:outline-none"
                                    >
                                      {link.label}
                                    </Link>
                                  </>
                                )}
                              </div>
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                              {isUnread && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  aria-label="Mark as read"
                                  disabled={markRead.isPending}
                                  onClick={() => handleMarkRead(n.id)}
                                >
                                  <CheckCheck
                                    strokeWidth={1.5}
                                    className="size-4 text-ink-500"
                                  />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                aria-label="Archive"
                                disabled={archive.isPending}
                                onClick={() => handleArchive(n.id)}
                              >
                                <Archive
                                  strokeWidth={1.5}
                                  className="size-4 text-ink-500"
                                />
                              </Button>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  </Card>
                </section>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
