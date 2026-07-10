import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { useQueryClient } from "@tanstack/react-query"
import { Archive, BellOff, CheckCheck, Loader2 } from "lucide-react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { orgPath } from "@/lib/investorRoutes"
import { config } from "@edenscale/api/config"
import { formatDate, titleCase } from "@edenscale/shared/format"
import { cn } from "@edenscale/shared/utils"
import type { components } from "@edenscale/api/schema"

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
  related_id: string | null,
  orgSlug: string | null,
): { to: string; label: string } | null {
  if (!related_type || related_id === null || !orgSlug) return null
  switch (related_type) {
    case "capital_call":
      return { to: orgPath(orgSlug, "calls"), label: "View capital calls" }
    case "distribution":
      return { to: orgPath(orgSlug, "distributions"), label: "View distributions" }
    case "document":
      return { to: orgPath(orgSlug, "documents"), label: "View documents" }
    case "communication":
    case "letter":
      return { to: orgPath(orgSlug, "letters"), label: "View letters" }
    default:
      return null
  }
}

export default function NotificationsPage() {
  const queryClient = useQueryClient()
  const { activeOrganization } = useInvestorOrganizations()
  const orgSlug = activeOrganization?.organization.slug ?? null

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

  const markRead = useApiMutation("post", "/notifications/{notification_id}/read")
  const archive = useApiMutation("post", "/notifications/{notification_id}/archive")
  const markAllRead = useApiMutation("post", "/notifications/read-all")

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["/notifications"] })
    queryClient.invalidateQueries({ queryKey: ["/investor/dashboard/overview"] })
  }

  async function handleMarkRead(notificationId: string) {
    try {
      await markRead.mutateAsync({
        params: { path: { notification_id: notificationId } },
      })
      invalidate()
    } catch {
      // toast surfaced by useApiMutation
    }
  }

  async function handleArchive(notificationId: string) {
    try {
      await archive.mutateAsync({
        params: { path: { notification_id: notificationId } },
      })
      toast.success("Notification archived")
      invalidate()
    } catch {
      // toast surfaced by useApiMutation
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
      // toast surfaced by useApiMutation
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
        description="Capital activity, document releases, and correspondence from your fund managers."
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

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {notificationsQuery.isLoading ? (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : inbox.length === 0 ? (
          <Card>
            <EmptyState
              icon={<BellOff strokeWidth={1.25} />}
              title="All caught up"
              body="There are no notifications in your inbox. Capital activity and correspondence will appear here."
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
                        const link = relatedLink(n.related_type, n.related_id, orgSlug)
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
                                {n.created_at && <span>{formatDate(n.created_at)}</span>}
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
