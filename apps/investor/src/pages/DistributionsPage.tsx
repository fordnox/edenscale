import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Loader2 } from "lucide-react"

import { NoticeDetailSheet } from "@/components/NoticeDetailSheet"
import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
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

export default function DistributionsPage() {
  const distributionsQuery = useApiQuery("/investor/distributions")
  const distributions = useMemo(
    () => distributionsQuery.data ?? [],
    [distributionsQuery.data],
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = useMemo(
    () => distributions.find((d) => d.id === selectedId) ?? null,
    [distributions, selectedId],
  )

  const summary = useMemo(() => {
    let lifetimeTotal = 0
    let paidTotal = 0
    for (const d of distributions) {
      lifetimeTotal += (d.items ?? []).reduce(
        (acc, item) => acc + parseDecimal(item.amount_due),
        0,
      )
      paidTotal += (d.items ?? []).reduce(
        (acc, item) => acc + parseDecimal(item.amount_paid),
        0,
      )
    }
    return { lifetimeTotal, paidTotal }
  }, [distributions])

  return (
    <>
      <Helmet>
        <title>{`Distributions · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Distributions"
        title="What has been returned."
        description="Distribution notices for your commitments. Amounts shown are your share of each distribution."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          <div className="grid grid-cols-2">
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Lifetime distributed"
                value={formatCurrency(summary.lifetimeTotal, "USD", { compact: true })}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Received to date"
                value={formatCurrency(summary.paidTotal, "USD", { compact: true })}
              />
            </CardSection>
          </div>
        </Card>

        <Card className="mt-8">
          <CardSection className="pt-2 pb-0">
            {distributionsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : distributions.length === 0 ? (
              <EmptyState title="No distributions" body="You have no distributions yet." />
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Distribution</TH>
                    <TH>Fund</TH>
                    <TH align="right">Date</TH>
                    <TH align="right">Your amount</TH>
                    <TH align="right">Received</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {distributions.map((distribution) => {
                    const due = (distribution.items ?? []).reduce(
                      (acc, item) => acc + parseDecimal(item.amount_due),
                      0,
                    )
                    const paid = (distribution.items ?? []).reduce(
                      (acc, item) => acc + parseDecimal(item.amount_paid),
                      0,
                    )
                    const paidPct = due > 0 ? Math.min(paid / due, 1) : 0
                    return (
                      <TR
                        key={distribution.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(distribution.id)}
                      >
                        <TD primary>{distribution.title}</TD>
                        <TD>{distribution.fund.name}</TD>
                        <TD align="right">
                          {formatDate(distribution.distribution_date)}
                        </TD>
                        <TD align="right" primary>
                          {formatCurrency(due, distribution.fund.currency_code, {
                            compact: true,
                          })}
                        </TD>
                        <TD align="right">
                          <div className="flex flex-col items-end gap-1.5">
                            <span className="es-numeric text-[13px] text-ink-900">
                              {Math.round(paidPct * 100)}%
                            </span>
                            <ProgressBar value={paidPct} className="w-[80px]" tone="brand" />
                          </div>
                        </TD>
                        <TD align="right">
                          <StatusPill kind="distribution" value={distribution.status} />
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
        notice={selected ? { kind: "distribution", record: selected } : null}
        onClose={() => setSelectedId(null)}
      />
    </>
  )
}
