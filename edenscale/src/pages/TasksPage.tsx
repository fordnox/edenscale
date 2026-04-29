import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Eyebrow } from "@/components/ui/eyebrow"
import { tasks, type TaskStatus } from "@/data/mock"
import { formatDate } from "@/lib/format"

const lanes: Array<{ id: TaskStatus; label: string }> = [
  { id: "open", label: "Open" },
  { id: "in_progress", label: "In progress" },
  { id: "done", label: "Done" },
]

export function TasksPage() {
  return (
    <>
      <Topbar
        eyebrow="Workflow"
        title="Tasks across the firm."
        description="Open items assigned across investor relations, compliance, and finance."
        actions={
          <Button variant="primary" size="sm">New task</Button>
        }
      />

      <div className="px-8 pb-16">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {lanes.map((lane) => {
            const items = tasks.filter((t) => t.status === lane.id)
            return (
              <Card key={lane.id} className="flex flex-col">
                <div className="flex items-center justify-between px-6 pt-6 md:px-7 md:pt-7">
                  <Eyebrow>{lane.label}</Eyebrow>
                  <span className="font-sans text-[12px] text-ink-500">
                    {items.length}
                  </span>
                </div>
                <CardSection className="flex flex-1 flex-col gap-3 pt-4">
                  {items.length === 0 && (
                    <p className="font-sans text-[13px] text-ink-500">
                      Nothing here.
                    </p>
                  )}
                  {items.map((t) => (
                    <article
                      key={t.id}
                      className="flex flex-col gap-3 border border-[color:var(--border-hairline)] bg-page p-4 hover:border-[color:var(--border-default)]"
                    >
                      <span className="font-sans text-[14px] leading-[1.4] text-ink-900">
                        {t.title}
                      </span>
                      <div className="flex flex-wrap items-center gap-2 font-sans text-[11px] text-ink-500">
                        {t.fund_name && <span>{t.fund_name}</span>}
                        {t.fund_name && t.due_date && (
                          <span className="size-1 rounded-full bg-ink-300" />
                        )}
                        {t.due_date && <span>Due {formatDate(t.due_date)}</span>}
                      </div>
                      <div className="flex items-center justify-between border-t border-[color:var(--border-hairline)] pt-3">
                        <span className="font-sans text-[11px] text-ink-500">
                          {t.assigned_to}
                        </span>
                        <StatusBadge status={t.status} />
                      </div>
                    </article>
                  ))}
                </CardSection>
              </Card>
            )
          })}
        </div>
      </div>
    </>
  )
}
