import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Loader2 } from "lucide-react"

import { NoticeDetailSheet } from "@/components/NoticeDetailSheet"
import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatDate } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const OPEN_STATUSES = ["scheduled", "sent", "partially_paid", "overdue"]

export default function CapitalCallsPage() {
  const callsQuery = useApiQuery("/capital-calls")
  const calls = useMemo(() => callsQuery.data ?? [], [callsQuery.data])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(
    () => calls.find((c) => c.id === selectedId) ?? null,
    [calls, selectedId],
  )

  const summary = useMemo(() => {
    let openCount = 0
    let openTotal = 0
    let lifetimeTotal = 0
    let paidTotal = 0
    for (const c of calls) {
      // LPs only receive their own allocation items — their figures are their
      // share of each call, not the fund-level amount.
      const due = (c.items ?? []).reduce(
        (acc, item) => acc + parseDecimal(item.amount_due),
        0,
      )
      const paid = (c.items ?? []).reduce(
        (acc, item) => acc + parseDecimal(item.amount_paid),
        0,
      )
      lifetimeTotal += due
      paidTotal += paid
      if (OPEN_STATUSES.includes(c.status)) {
        openCount += 1
        openTotal += due - paid
      }
    }
    return { openCount, openTotal, lifetimeTotal, paidTotal }
  }, [calls])

  return (
    <>
      <Helmet>
        <title>{`Capital calls · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Capital calls"
        title="What has been called."
        description="Drawdown notices for your commitments. Amounts shown are your share of each call."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-3">
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Outstanding"
                value={formatCurrency(summary.openTotal, "USD", { compact: true })}
                caption={`${summary.openCount} open call${summary.openCount === 1 ? "" : "s"}`}
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Lifetime called"
                value={formatCurrency(summary.lifetimeTotal, "USD", { compact: true })}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Lifetime paid"
                value={formatCurrency(summary.paidTotal, "USD", { compact: true })}
              />
            </CardSection>
          </div>
        </Card>

        <Card className="mt-8">
          <CardSection className="pt-2 pb-0">
            {callsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : calls.length === 0 ? (
              <EmptyState title="No capital calls" body="You have no capital calls yet." />
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Call</TH>
                    <TH>Fund</TH>
                    <TH align="right">Due</TH>
                    <TH align="right">Your amount</TH>
                    <TH align="right">Paid</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => {
                    const due = (call.items ?? []).reduce(
                      (acc, item) => acc + parseDecimal(item.amount_due),
                      0,
                    )
                    const paid = (call.items ?? []).reduce(
                      (acc, item) => acc + parseDecimal(item.amount_paid),
                      0,
                    )
                    const paidPct = due > 0 ? Math.min(paid / due, 1) : 0
                    return (
                      <TR
                        key={call.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(call.id)}
                      >
                        <TD primary>{call.title}</TD>
                        <TD>{call.fund.name}</TD>
                        <TD align="right">{formatDate(call.due_date)}</TD>
                        <TD align="right" primary>
                          {formatCurrency(due, call.fund.currency_code, {
                            compact: true,
                          })}
                        </TD>
                        <TD align="right">
                          <div className="flex flex-col items-end gap-1.5">
                            <span className="es-numeric text-[13px] text-ink-900">
                              {Math.round(paidPct * 100)}%
                            </span>
                            <ProgressBar
                              value={paidPct}
                              className="w-[80px]"
                              tone={call.status === "overdue" ? "brass" : "brand"}
                            />
                          </div>
                        </TD>
                        <TD align="right">
                          <StatusPill kind="capital_call" value={call.status} />
                        </TD>
                      </TR>
                    )
                  })}
                </tbody>
              </DataTable>
            )}
          </CardSection>
        </Card>
      </div>

      <NoticeDetailSheet
        notice={selected ? { kind: "capital_call", record: selected } : null}
        onClose={() => setSelectedId(null)}
      />
    </>
  )
}
