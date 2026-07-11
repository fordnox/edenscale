import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Loader2 } from "lucide-react"

import { DistributionCreateDialog } from "@/components/distributions/DistributionCreateDialog"
import { DistributionDetail } from "@/components/distributions/DistributionDetail"
import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatDate } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type DistributionStatus = components["schemas"]["DistributionStatus"]

const STATUS_OPTIONS: Array<{
  value: "all" | DistributionStatus
  label: string
}> = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "scheduled", label: "Scheduled" },
  { value: "sent", label: "Sent" },
  { value: "partially_paid", label: "Partially paid" },
  { value: "paid", label: "Paid" },
  { value: "cancelled", label: "Cancelled" },
]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function DistributionsPage() {
  const { activeMembership } = useActiveOrganization()
  const canManage =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  const [createOpen, setCreateOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fundFilter, setFundFilter] = useState<"all" | string>("all")
  const [statusFilter, setStatusFilter] = useState<"all" | DistributionStatus>(
    "all",
  )

  const fundsQuery = useApiQuery("/funds")
  const distributionsQuery = useApiQuery("/distributions", {
    params: {
      query: {
        ...(fundFilter !== "all" ? { fund_id: fundFilter } : {}),
        ...(statusFilter !== "all" ? { status_filter: statusFilter } : {}),
      },
    },
  })

  const distributions = useMemo(
    () => distributionsQuery.data ?? [],
    [distributionsQuery.data],
  )
  const allDistributionsQuery = useApiQuery("/distributions")
  const allDistributions = useMemo(
    () => allDistributionsQuery.data ?? [],
    [allDistributionsQuery.data],
  )

  const summary = useMemo(() => {
    let openCount = 0
    let openTotal = 0
    let lifetimeTotal = 0
    let paidTotal = 0
    for (const d of allDistributions) {
      // LPs only receive their own allocation items, so their figures are
      // their share of each distribution rather than the fund-level amount.
      const amount = canManage
        ? parseDecimal(d.amount)
        : (d.items ?? []).reduce(
            (acc, item) => acc + parseDecimal(item.amount_due),
            0,
          )
      lifetimeTotal += amount
      const itemsPaid = (d.items ?? []).reduce(
        (acc, item) => acc + parseDecimal(item.amount_paid),
        0,
      )
      paidTotal += itemsPaid
      if (["scheduled", "sent", "partially_paid"].includes(d.status)) {
        openCount += 1
        openTotal += amount - itemsPaid
      }
    }
    return {
      openCount,
      openTotal,
      lifetimeTotal,
      paidTotal,
      paidPct: lifetimeTotal > 0 ? paidTotal / lifetimeTotal : 0,
    }
  }, [allDistributions, canManage])

  return (
    <>
      <Helmet>
        <title>{`Distributions · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Distributions"
        title="Returns to limited partners."
        description="Cash distributed across funds. Status updates as wires settle."
        actions={
          canManage ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setCreateOpen(true)}
            >
              New distribution
            </Button>
          ) : undefined
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Open distributions"
                value={summary.openCount}
                caption={`${formatCurrency(summary.openTotal, "USD", { compact: true })} outstanding`}
              />
            </CardSection>
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Events"
                value={allDistributions.length}
                caption={
                  allDistributions.length === 1 ? "distribution" : "distributions"
                }
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Lifetime distributed"
                value={formatCurrency(summary.lifetimeTotal, "USD", {
                  compact: true,
                })}
                caption={`${allDistributions.length} events`}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Lifetime paid"
                value={formatCurrency(summary.paidTotal, "USD", {
                  compact: true,
                })}
                caption={`${Math.round(summary.paidPct * 100)}% of distributed`}
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
                setStatusFilter(value as "all" | DistributionStatus)
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
            {distributions.length} distribution
            {distributions.length === 1 ? "" : "s"}
          </span>
        </div>

        <Card>
          <CardSection className="pt-2 pb-0">
            {distributionsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : distributions.length === 0 ? (
              <div className="flex flex-col items-start gap-2 py-8">
                <Eyebrow>No distributions match these filters</Eyebrow>
                <p className="font-sans text-[14px] text-ink-700">
                  Try a different fund or status.
                </p>
              </div>
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Distribution</TH>
                    <TH>Fund</TH>
                    <TH align="right">Date</TH>
                    <TH align="right">Amount</TH>
                    <TH align="right">Paid</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {distributions.map((distribution) => {
                    const amount = canManage
                      ? parseDecimal(distribution.amount)
                      : (distribution.items ?? []).reduce(
                          (acc, item) => acc + parseDecimal(item.amount_due),
                          0,
                        )
                    const paid = (distribution.items ?? []).reduce(
                      (acc, item) => acc + parseDecimal(item.amount_paid),
                      0,
                    )
                    const paidPct =
                      amount > 0 ? Math.min(paid / amount, 1) : 0
                    return (
                      <TR
                        key={distribution.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(distribution.id)}
                      >
                        <TD primary>
                          <div className="flex flex-col gap-1">
                            <span>{distribution.title}</span>
                            <span className="font-sans text-[11px] font-normal text-ink-500">
                              {canManage
                                ? `${(distribution.items ?? []).length} limited partners`
                                : "Your share"}
                            </span>
                          </div>
                        </TD>
                        <TD>{distribution.fund.name}</TD>
                        <TD align="right">
                          {formatDate(distribution.distribution_date)}
                        </TD>
                        <TD align="right" primary>
                          {formatCurrency(
                            amount,
                            distribution.fund.currency_code,
                            { compact: true },
                          )}
                        </TD>
                        <TD align="right">
                          <div className="flex flex-col items-end gap-1.5">
                            <span className="es-numeric text-[13px] text-ink-900">
                              {Math.round(paidPct * 100)}%
                            </span>
                            <ProgressBar
                              value={paidPct}
                              className="w-[80px]"
                              tone="brand"
                            />
                          </div>
                        </TD>
                        <TD align="right">
                          <StatusPill
                            kind="distribution"
                            value={distribution.status}
                          />
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
          <SheetTitle className="sr-only">Distribution detail</SheetTitle>
          <SheetDescription className="sr-only">
            Allocations and actions for the selected distribution.
          </SheetDescription>
          {selectedId !== null && (
            <DistributionDetail
              key={selectedId}
              distributionId={selectedId}
            />
          )}
        </SheetContent>
      </Sheet>

      <DistributionCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => setSelectedId(id)}
      />
    </>
  )
}
