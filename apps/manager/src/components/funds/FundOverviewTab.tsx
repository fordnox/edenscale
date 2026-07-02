import { useMemo } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts"

import { Card, CardSection } from "@edenscale/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@edenscale/ui/chart"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import {
  formatCurrency,
  formatDate,
  formatDateLong,
  formatPercent,
  titleCase,
} from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type FundRead = components["schemas"]["FundRead"]
type FundOverview = components["schemas"]["FundOverview"]
type CapitalCallRead = components["schemas"]["CapitalCallRead"]
type DistributionRead = components["schemas"]["DistributionRead"]
type CommitmentRead = components["schemas"]["CommitmentRead"]

// Muted brand tones (conifer-500 / brass-500). See dataviz note: intentionally
// low-chroma to match the product palette; the two-series chart carries a legend
// as secondary encoding.
const CALLED_COLOR = "#3a5c46"
const DISTRIBUTED_COLOR = "#b8915c"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const activityConfig = {
  called: { label: "Called", color: CALLED_COLOR },
  distributed: { label: "Distributed", color: DISTRIBUTED_COLOR },
} satisfies ChartConfig

const countConfig = {
  count: { label: "Calls", color: CALLED_COLOR },
} satisfies ChartConfig

const committedConfig = {
  committed: { label: "Committed", color: CALLED_COLOR },
} satisfies ChartConfig

interface FundOverviewTabProps {
  fund: FundRead
  overview: FundOverview | undefined
  calls: readonly CapitalCallRead[]
  distributions: readonly DistributionRead[]
  commitments: readonly CommitmentRead[]
}

export function FundOverviewTab({
  fund,
  overview,
  calls,
  distributions,
  commitments,
}: FundOverviewTabProps) {
  const currency = fund.currency_code

  const committed = parseDecimal(overview?.committed)
  const called = parseDecimal(overview?.called)
  const distributed = parseDecimal(overview?.distributed)
  const remaining = parseDecimal(overview?.remaining_commitment)
  const calledPct = committed > 0 ? called / committed : 0
  const targetSize = parseDecimal(fund.target_size)
  const targetPct = targetSize > 0 ? Math.min(committed / targetSize, 1) : 0

  const dpiLabel =
    overview?.dpi != null ? `${parseDecimal(overview.dpi).toFixed(2)}x` : "—"
  const irrLabel =
    overview?.irr != null ? formatPercent(parseDecimal(overview.irr)) : "—"
  const calledPctLabel =
    overview?.called_pct != null
      ? formatPercent(parseDecimal(overview.called_pct))
      : committed > 0
        ? formatPercent(calledPct)
        : "—"

  // Cumulative called vs distributed, built from paid line items over time.
  const activitySeries = useMemo(() => {
    type Event = { date: string; called: number; distributed: number }
    const events: Event[] = []
    for (const call of calls) {
      for (const item of call.items ?? []) {
        const paid = parseDecimal(item.amount_paid)
        if (item.paid_at && paid > 0) {
          events.push({ date: item.paid_at, called: paid, distributed: 0 })
        }
      }
    }
    for (const dist of distributions) {
      for (const item of dist.items ?? []) {
        const paid = parseDecimal(item.amount_paid)
        if (item.paid_at && paid > 0) {
          events.push({ date: item.paid_at, called: 0, distributed: paid })
        }
      }
    }
    events.sort((a, b) => a.date.localeCompare(b.date))

    const byDate = new Map<string, { called: number; distributed: number }>()
    for (const ev of events) {
      const existing = byDate.get(ev.date) ?? { called: 0, distributed: 0 }
      existing.called += ev.called
      existing.distributed += ev.distributed
      byDate.set(ev.date, existing)
    }

    let cumCalled = 0
    let cumDistributed = 0
    return Array.from(byDate.entries()).map(([date, totals]) => {
      cumCalled += totals.called
      cumDistributed += totals.distributed
      return { date, called: cumCalled, distributed: cumDistributed }
    })
  }, [calls, distributions])

  const callsByStatus = useMemo(() => {
    const counts = new Map<string, number>()
    for (const call of calls) {
      counts.set(call.status, (counts.get(call.status) ?? 0) + 1)
    }
    return Array.from(counts.entries()).map(([status, count]) => ({
      status,
      label: titleCase(status),
      count,
    }))
  }, [calls])

  const commitmentsByInvestor = useMemo(() => {
    return commitments
      .map((c) => ({
        name: c.investor.name,
        committed: parseDecimal(c.committed_amount),
      }))
      .sort((a, b) => b.committed - a.committed)
  }, [commitments])

  const currencyTooltipFormatter = (value: unknown, name: unknown) => {
    const cfg = activityConfig[name as keyof typeof activityConfig]
    return (
      <div className="flex w-full items-center justify-between gap-4">
        <span className="text-muted-foreground">{cfg?.label ?? String(name)}</span>
        <span className="font-mono font-medium tabular-nums text-foreground">
          {formatCurrency(Number(value), currency, { compact: true })}
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Fund information + pacing / inception */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardSection>
            <Eyebrow>Fund information</Eyebrow>
            <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <InfoRow label="Legal name" value={fund.legal_name} />
              <InfoRow label="Strategy" value={fund.strategy} />
              <InfoRow
                label="Vintage year"
                value={fund.vintage_year ? String(fund.vintage_year) : null}
              />
              <div className="flex flex-col gap-0.5">
                <dt className="font-sans text-[11px] uppercase tracking-[0.12em] text-ink-500">
                  Status
                </dt>
                <dd className="mt-1">
                  <StatusPill kind="fund" value={fund.status} />
                </dd>
              </div>
              <InfoRow
                label="Inception date"
                value={
                  fund.inception_date
                    ? formatDateLong(fund.inception_date)
                    : null
                }
              />
              <InfoRow
                label="Close date"
                value={fund.close_date ? formatDateLong(fund.close_date) : null}
              />
            </dl>
            {fund.description && (
              <p className="mt-5 border-t border-[color:var(--border-hairline)] pt-4 font-sans text-[14px] leading-[1.55] text-ink-700">
                {fund.description}
              </p>
            )}
          </CardSection>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <CardSection>
              <Eyebrow>Pacing</Eyebrow>
              <p className="mt-3 font-sans text-[14px] leading-[1.55] text-ink-700">
                The fund has called {committed > 0 ? formatPercent(calledPct) : "—"}{" "}
                of committed capital
                {targetSize > 0
                  ? ` against a ${formatCurrency(targetSize, currency, { compact: true })} target`
                  : ""}
                .
              </p>
              <div className="mt-5 flex flex-col gap-2">
                <div className="flex justify-between font-sans text-[12px] text-ink-500">
                  <span>Called</span>
                  <span className="es-numeric">
                    {formatCurrency(called, currency, { compact: true })} ·{" "}
                    {formatCurrency(committed, currency, { compact: true })}
                  </span>
                </div>
                <ProgressBar value={calledPct} />
              </div>
              {targetSize > 0 && (
                <div className="mt-5 flex flex-col gap-2">
                  <div className="flex justify-between font-sans text-[12px] text-ink-500">
                    <span>Committed vs target</span>
                    <span className="es-numeric">{formatPercent(targetPct)}</span>
                  </div>
                  <ProgressBar value={targetPct} tone="brass" />
                </div>
              )}
            </CardSection>
          </Card>

          <Card raised>
            <CardSection>
              <Eyebrow>Inception</Eyebrow>
              <p className="mt-3 font-sans text-[14px] leading-[1.55] text-ink-700">
                {fund.inception_date
                  ? `Held since ${formatDateLong(fund.inception_date)}.`
                  : "Inception date not set."}{" "}
                Fund operates in {currency}.
              </p>
              {fund.close_date && (
                <p className="mt-2 font-sans text-[13px] text-ink-500">
                  Closes {formatDateLong(fund.close_date)}.
                </p>
              )}
            </CardSection>
          </Card>
        </div>
      </div>

      {/* Metric tiles */}
      <Card>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          <MetricCell label="Paid in" value={formatCurrency(called, currency, { compact: true })} border />
          <MetricCell label="Distributed" value={formatCurrency(distributed, currency, { compact: true })} border />
          <MetricCell label="DPI" value={dpiLabel} border />
          <MetricCell label="Net IRR" value={irrLabel} border />
          <MetricCell label="Called %" value={calledPctLabel} border />
          <MetricCell label="Remaining commitment" value={formatCurrency(remaining, currency, { compact: true })} />
        </div>
      </Card>

      {/* Capital activity over time */}
      <Card>
        <CardSection>
          <Eyebrow>Capital activity over time</Eyebrow>
          <p className="mt-2 font-sans text-[13px] text-ink-500">
            Cumulative capital called and distributed as wires settle.
          </p>
          <div className="mt-5">
            {activitySeries.length === 0 ? (
              <ChartEmpty message="No cashflows recorded yet." />
            ) : (
              <ChartContainer
                config={activityConfig}
                className="aspect-auto h-[280px] w-full"
              >
                <AreaChart data={activitySeries} margin={{ left: 4, right: 12, top: 8 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    minTickGap={24}
                    tickFormatter={(value: string) =>
                      formatDate(value, { day: "2-digit", month: "short" })
                    }
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    width={56}
                    tickFormatter={(value: number) =>
                      formatCurrency(value, currency, { compact: true })
                    }
                  />
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        formatter={currencyTooltipFormatter}
                        labelFormatter={(value) => formatDateLong(String(value))}
                      />
                    }
                  />
                  <Area
                    dataKey="called"
                    type="monotone"
                    stroke="var(--color-called)"
                    fill="var(--color-called)"
                    fillOpacity={0.12}
                    strokeWidth={2}
                  />
                  <Area
                    dataKey="distributed"
                    type="monotone"
                    stroke="var(--color-distributed)"
                    fill="var(--color-distributed)"
                    fillOpacity={0.12}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ChartContainer>
            )}
            {activitySeries.length > 0 && (
              <div className="mt-3 flex items-center justify-center gap-5">
                <LegendSwatch color={CALLED_COLOR} label="Called" />
                <LegendSwatch color={DISTRIBUTED_COLOR} label="Distributed" />
              </div>
            )}
          </div>
        </CardSection>
      </Card>

      {/* Bar charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardSection>
            <Eyebrow>Capital calls by status</Eyebrow>
            <div className="mt-5">
              {callsByStatus.length === 0 ? (
                <ChartEmpty message="No capital calls issued yet." />
              ) : (
                <ChartContainer
                  config={countConfig}
                  className="aspect-auto h-[240px] w-full"
                >
                  <BarChart data={callsByStatus} margin={{ left: 4, right: 12, top: 8 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey="label"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                    />
                    <YAxis
                      allowDecimals={false}
                      tickLine={false}
                      axisLine={false}
                      width={32}
                    />
                    <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                    <Bar
                      dataKey="count"
                      fill="var(--color-count)"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ChartContainer>
              )}
            </div>
          </CardSection>
        </Card>

        <Card>
          <CardSection>
            <Eyebrow>Commitments by investor</Eyebrow>
            <div className="mt-5">
              {commitmentsByInvestor.length === 0 ? (
                <ChartEmpty message="No commitments recorded yet." />
              ) : (
                <ChartContainer
                  config={committedConfig}
                  className="aspect-auto h-[240px] w-full"
                >
                  <BarChart data={commitmentsByInvestor} margin={{ left: 4, right: 12, top: 8 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey="name"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      interval={0}
                      height={48}
                      angle={-20}
                      textAnchor="end"
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      width={56}
                      tickFormatter={(value: number) =>
                        formatCurrency(value, currency, { compact: true })
                      }
                    />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          hideLabel
                          formatter={(value, _name, item) => (
                            <div className="flex w-full items-center justify-between gap-4">
                              <span className="text-muted-foreground">
                                {item?.payload?.name}
                              </span>
                              <span className="font-mono font-medium tabular-nums text-foreground">
                                {formatCurrency(Number(value), currency, {
                                  compact: true,
                                })}
                              </span>
                            </div>
                          )}
                        />
                      }
                    />
                    <Bar
                      dataKey="committed"
                      fill="var(--color-committed)"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ChartContainer>
              )}
            </div>
          </CardSection>
        </Card>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="font-sans text-[11px] uppercase tracking-[0.12em] text-ink-500">
        {label}
      </dt>
      <dd className="font-sans text-[14px] text-ink-900">{value ?? "—"}</dd>
    </div>
  )
}

function MetricCell({
  label,
  value,
  border = false,
}: {
  label: string
  value: string
  border?: boolean
}) {
  return (
    <CardSection
      className={
        border
          ? "border-b border-[color:var(--border-hairline)] sm:border-r"
          : ""
      }
    >
      <Stat label={label} value={value} />
    </CardSection>
  )
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className="size-2.5 rounded-[2px]"
        style={{ backgroundColor: color }}
      />
      <span className="font-sans text-[12px] text-ink-500">{label}</span>
    </div>
  )
}

function ChartEmpty({ message }: { message: string }) {
  return (
    <div className="flex h-[240px] items-center justify-center border border-dashed border-[color:var(--border-hairline)] bg-parchment-100/40">
      <p className="font-sans text-[13px] text-ink-500">{message}</p>
    </div>
  )
}
