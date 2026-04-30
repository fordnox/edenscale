import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Loader2 } from "lucide-react"

import { CapitalCallCreateDialog } from "@/components/capital-calls/CapitalCallCreateDialog"
import { CapitalCallDetail } from "@/components/capital-calls/CapitalCallDetail"
import { PageHero } from "@/components/layout/PageHero"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { ProgressBar } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet"
import { Stat } from "@/components/ui/stat"
import { StatusPill } from "@/components/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatCurrency, formatDate } from "@/lib/format"
import type { components } from "@/lib/schema"

type CapitalCallStatus = components["schemas"]["CapitalCallStatus"]

const STATUS_OPTIONS: Array<{ value: "all" | CapitalCallStatus; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "scheduled", label: "Scheduled" },
  { value: "sent", label: "Sent" },
  { value: "partially_paid", label: "Partially paid" },
  { value: "paid", label: "Paid" },
  { value: "overdue", label: "Overdue" },
  { value: "cancelled", label: "Cancelled" },
]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function CapitalCallsPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [fundFilter, setFundFilter] = useState<"all" | string>("all")
  const [statusFilter, setStatusFilter] = useState<"all" | CapitalCallStatus>(
    "all",
  )

  const fundsQuery = useApiQuery("/funds")
  const callsQuery = useApiQuery("/capital-calls", {
    params: {
      query: {
        ...(fundFilter !== "all" ? { fund_id: Number(fundFilter) } : {}),
        ...(statusFilter !== "all" ? { status_filter: statusFilter } : {}),
      },
    },
  })

  const calls = useMemo(() => callsQuery.data ?? [], [callsQuery.data])
  const allCallsQuery = useApiQuery("/capital-calls")
  const allCalls = useMemo(() => allCallsQuery.data ?? [], [allCallsQuery.data])

  const summary = useMemo(() => {
    let openCount = 0
    let overdueCount = 0
    let openTotal = 0
    let lifetimeTotal = 0
    let paidTotal = 0
    for (const c of allCalls) {
      const amount = parseDecimal(c.amount)
      lifetimeTotal += amount
      const itemsPaid = (c.items ?? []).reduce(
        (acc, item) => acc + parseDecimal(item.amount_paid),
        0,
      )
      paidTotal += itemsPaid
      if (
        ["scheduled", "sent", "partially_paid", "overdue"].includes(c.status)
      ) {
        openCount += 1
        openTotal += amount - itemsPaid
      }
      if (c.status === "overdue") overdueCount += 1
    }
    return {
      openCount,
      overdueCount,
      openTotal,
      lifetimeTotal,
      paidTotal,
      paidPct: lifetimeTotal > 0 ? paidTotal / lifetimeTotal : 0,
    }
  }, [allCalls])

  return (
    <>
      <Helmet>
        <title>{`Capital calls · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Capital calls"
        title="What we have called, and what awaits."
        description="Drawdowns issued across funds. Status updates as wires settle."
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            New capital call
          </Button>
        }
      />

      <div className="px-8 pb-16">
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Open calls"
                value={summary.openCount}
                caption={`${formatCurrency(summary.openTotal, "USD", { compact: true })} outstanding`}
              />
            </CardSection>
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Overdue"
                value={summary.overdueCount}
                trend={summary.overdueCount > 0 ? "down" : "flat"}
                trendLabel={
                  summary.overdueCount > 0 ? "needs attention" : "all current"
                }
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Lifetime called"
                value={formatCurrency(summary.lifetimeTotal, "USD", {
                  compact: true,
                })}
                caption={`${allCalls.length} calls issued`}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Lifetime paid"
                value={formatCurrency(summary.paidTotal, "USD", {
                  compact: true,
                })}
                caption={`${Math.round(summary.paidPct * 100)}% of called`}
              />
            </CardSection>
          </div>
        </Card>

        <div className="mt-8 mb-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Eyebrow>Fund</Eyebrow>
            <Select value={fundFilter} onValueChange={setFundFilter}>
              <SelectTrigger className="min-w-[200px]">
                <SelectValue placeholder="All funds" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All funds</SelectItem>
                {(fundsQuery.data ?? []).map((fund) => (
                  <SelectItem key={fund.id} value={String(fund.id)}>
                    {fund.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Eyebrow>Status</Eyebrow>
            <Select
              value={statusFilter}
              onValueChange={(value) =>
                setStatusFilter(value as "all" | CapitalCallStatus)
              }
            >
              <SelectTrigger className="min-w-[180px]">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <span className="ml-auto font-sans text-[12px] text-ink-500">
            {calls.length} call{calls.length === 1 ? "" : "s"}
          </span>
        </div>

        <Card>
          <CardSection className="pt-2 pb-0">
            {callsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : calls.length === 0 ? (
              <div className="flex flex-col items-start gap-2 py-8">
                <Eyebrow>No capital calls match these filters</Eyebrow>
                <p className="font-sans text-[14px] text-ink-700">
                  Try a different fund or status.
                </p>
              </div>
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Call</TH>
                    <TH>Fund</TH>
                    <TH align="right">Due</TH>
                    <TH align="right">Amount</TH>
                    <TH align="right">Paid</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => {
                    const amount = parseDecimal(call.amount)
                    const paid = (call.items ?? []).reduce(
                      (acc, item) => acc + parseDecimal(item.amount_paid),
                      0,
                    )
                    const paidPct = amount > 0 ? Math.min(paid / amount, 1) : 0
                    return (
                      <TR
                        key={call.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(call.id)}
                      >
                        <TD primary>
                          <div className="flex flex-col gap-1">
                            <span>{call.title}</span>
                            <span className="font-sans text-[11px] font-normal text-ink-500">
                              {(call.items ?? []).length} limited partners
                            </span>
                          </div>
                        </TD>
                        <TD>{call.fund.name}</TD>
                        <TD align="right">{formatDate(call.due_date)}</TD>
                        <TD align="right" primary>
                          {formatCurrency(amount, call.fund.currency_code, {
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

      <Sheet
        open={selectedId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Capital call detail</SheetTitle>
          <SheetDescription className="sr-only">
            Allocations and actions for the selected capital call.
          </SheetDescription>
          {selectedId !== null && (
            <CapitalCallDetail key={selectedId} callId={selectedId} />
          )}
        </SheetContent>
      </Sheet>

      <CapitalCallCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => setSelectedId(id)}
      />
    </>
  )
}
