import { Topbar } from "@/components/layout/Topbar"
import { Card } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Button } from "@/components/ui/button"
import { notifications } from "@/data/mock"
import { formatDate } from "@/lib/format"
import { titleCase } from "@/lib/format"

export function NotificationsPage() {
  const unread = notifications.filter((n) => n.status === "unread")
  const read = notifications.filter((n) => n.status !== "unread")

  return (
    <>
      <Topbar
        eyebrow="Inbox"
        title="What is new."
        description="Capital activity, document releases, and investor correspondence."
        actions={
          <Button variant="secondary" size="sm">Mark all as read</Button>
        }
      />

      <div className="px-8 pb-16">
        {unread.length > 0 && (
          <>
            <div className="mb-4 flex items-end justify-between">
              <Eyebrow>Unread</Eyebrow>
              <span className="font-sans text-[12px] text-ink-500">
                {unread.length}
              </span>
            </div>
            <Card>
              <ul className="divide-y divide-[color:var(--border-hairline)]">
                {unread.map((n) => (
                  <li
                    key={n.id}
                    className="flex items-start gap-4 px-6 py-5 md:px-8"
                  >
                    <span className="mt-2 inline-block size-2 shrink-0 rounded-full bg-brass-500" />
                    <div className="flex flex-1 flex-col gap-1.5">
                      <span className="font-sans text-[15px] font-semibold tracking-[-0.005em] text-ink-900">
                        {n.title}
                      </span>
                      <p className="font-sans text-[14px] leading-[1.55] text-ink-700">
                        {n.message}
                      </p>
                      <div className="mt-1 flex items-center gap-2 font-sans text-[11px] text-ink-500">
                        <span>{titleCase(n.related_type)}</span>
                        <span className="size-1 rounded-full bg-ink-300" />
                        <span>{formatDate(n.created_at)}</span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          </>
        )}

        <div className={unread.length > 0 ? "mt-10" : ""}>
          <div className="mb-4 flex items-end justify-between">
            <Eyebrow>Earlier</Eyebrow>
            <span className="font-sans text-[12px] text-ink-500">
              {read.length}
            </span>
          </div>
          <Card>
            <ul className="divide-y divide-[color:var(--border-hairline)]">
              {read.map((n) => (
                <li
                  key={n.id}
                  className="flex items-start gap-4 px-6 py-5 md:px-8 opacity-80"
                >
                  <span className="mt-2 inline-block size-2 shrink-0 rounded-full bg-ink-300" />
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="font-sans text-[14px] font-medium text-ink-900">
                      {n.title}
                    </span>
                    <p className="font-sans text-[13px] leading-[1.55] text-ink-700">
                      {n.message}
                    </p>
                    <div className="mt-1 flex items-center gap-2 font-sans text-[11px] text-ink-500">
                      <span>{titleCase(n.related_type)}</span>
                      <span className="size-1 rounded-full bg-ink-300" />
                      <span>{formatDate(n.created_at)}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  )
}
