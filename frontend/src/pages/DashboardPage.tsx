import { useQuery } from "@tanstack/react-query"
import { Loader2, ArrowDownToLine } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { Helmet } from "react-helmet-async"

import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { Stat } from "@/components/ui/stat"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/badge"
import { ProgressBar } from "@/components/ui/progress"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import api from "@/lib/api"
import { config } from "@/lib/config"
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatRelativeDays,
} from "@/lib/format"

const TODAY = new Date()

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function DashboardPage() {
  const navigate = useNavigate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: async () => {
      const { data, error } = await api.GET("/dashboard/overview")
      if (error) throw error
      return data
    },
  })

  const overview = data
  const totalCommitted = parseDecimal(overview?.commitments_total_amount)
  const distributionsYtd = parseDecimal(overview?.distributions_ytd_amount)

  return (
    <>
      <Helmet>
        <title>{`Overview · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <Topbar
        eyebrow={formatDate(TODAY, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        title="Welcome back."
        description="A snapshot of activity across your funds, limited partners, and capital movements."
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => navigate("/calls")}>
              View capital calls
            </Button>
            <Button variant="primary" size="sm" onClick={() => navigate("/letters")}>
              Draft quarterly letter
            </Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        {isLoading && (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        )}

        {isError && !isLoading && (
          <Card>
            <CardSection>
              <Eyebrow>Could not load overview</Eyebrow>
              <p className="mt-3 font-sans text-[14px] text-ink-700">
                We were unable to fetch your dashboard data. Please refresh, or try again in a moment.
              </p>
            </CardSection>
          </Card>
        )}

        {!isLoading && !isError && overview && (
          <>
            <Card>
              <div className="grid grid-cols-1 gap-0 md:grid-cols-4">
                <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
                  <Stat
                    label="Active funds"
                    value={overview.funds_active}
                    caption={`${overview.investors_total} limited partners`}
                  />
                </CardSection>
                <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
                  <Stat
                    label="Total committed"
                    value={formatCurrency(totalCommitted, "USD", { compact: true })}
                    caption="Across all funds in scope"
                  />
                </CardSection>
                <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
                  <Stat
                    label="Capital calls outstanding"
                    value={overview.capital_calls_outstanding}
                    caption="Scheduled, sent, or overdue"
                  />
                </CardSection>
                <CardSection>
                  <Stat
                    label="Distributions YTD"
                    value={formatCurrency(distributionsYtd, "USD", { compact: true })}
                    caption={`Year ${TODAY.getFullYear()}`}
                  />
                </CardSection>
              </div>
            </Card>

            <div className="mt-8">
              <Card>
                <div className="flex items-end justify-between gap-4 px-6 pt-7 md:px-8 md:pt-8">
                  <div className="flex flex-col gap-2">
                    <Eyebrow>Upcoming</Eyebrow>
                    <h2 className="es-display text-[28px]">
                      Capital calls awaiting attention.
                    </h2>
                  </div>
                  <button
                    type="button"
                    className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700 transition-colors"
                    onClick={() => navigate("/calls")}
                  >
                    Open all →
                  </button>
                </div>
                <CardSection className="pt-5">
                  {overview.upcoming_capital_calls.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-8">
                      <Eyebrow>All clear</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        No outstanding capital calls. New calls will appear here as soon as they are scheduled.
                      </p>
                    </div>
                  ) : (
                    <DataTable>
                      <thead>
                        <tr>
                          <TH>Call</TH>
                          <TH>Fund</TH>
                          <TH align="right">Amount</TH>
                          <TH align="right">Due</TH>
                          <TH align="right">Status</TH>
                        </tr>
                      </thead>
                      <tbody>
                        {overview.upcoming_capital_calls.map((call) => (
                          <TR key={call.id}>
                            <TD primary>
                              <div className="flex items-center gap-3">
                                <span className="inline-flex size-7 shrink-0 items-center justify-center border border-brass-500 text-brass-700">
                                  <ArrowDownToLine strokeWidth={1.5} className="size-3.5" />
                                </span>
                                <span className="leading-tight">{call.title}</span>
                              </div>
                            </TD>
                            <TD>{call.fund_name}</TD>
                            <TD align="right" primary>
                              {formatCurrency(parseDecimal(call.amount), "USD", { compact: true })}
                            </TD>
                            <TD align="right">
                              <div className="flex flex-col items-end leading-tight">
                                <span className="text-ink-900 text-[14px]">
                                  {formatDate(call.due_date)}
                                </span>
                                <span className="text-[11px] text-ink-500">
                                  {formatRelativeDays(call.due_date, TODAY)}
                                </span>
                              </div>
                            </TD>
                            <TD align="right">
                              <StatusBadge status={call.status} />
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </CardSection>
              </Card>
            </div>

            <div className="mt-12">
              <div className="mb-6 flex items-end justify-between gap-4">
                <div className="flex flex-col gap-2">
                  <Eyebrow>Recent funds</Eyebrow>
                  <h2 className="es-display text-[32px]">
                    Programmes in flight.
                  </h2>
                </div>
                <Button variant="link" size="sm" onClick={() => navigate("/funds")}>
                  All funds →
                </Button>
              </div>

              {overview.recent_funds.length === 0 ? (
                <Card>
                  <CardSection className="flex flex-col gap-2">
                    <Eyebrow>No funds yet</Eyebrow>
                    <p className="font-sans text-[14px] text-ink-700 max-w-xl">
                      Once your firm sets up its first fund, it will appear here with committed and called capital figures.
                    </p>
                  </CardSection>
                </Card>
              ) : (
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {overview.recent_funds.map((fund) => {
                    const committed = parseDecimal(fund.committed_amount)
                    const called = parseDecimal(fund.called_amount)
                    const calledPct = committed > 0 ? called / committed : 0
                    const tvpi = parseDecimal(fund.tvpi)
                    const irr = parseDecimal(fund.irr)
                    return (
                      <Card key={fund.id} className="flex flex-col">
                        <CardSection className="flex flex-1 flex-col gap-5">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex flex-col gap-1.5">
                              {fund.vintage_year && (
                                <Eyebrow>Vintage {fund.vintage_year}</Eyebrow>
                              )}
                              <h3 className="font-display text-[26px] font-medium leading-[1.1] tracking-[-0.015em] text-ink-900">
                                {fund.name}
                              </h3>
                            </div>
                            <StatusBadge status={fund.status} />
                          </div>
                          {fund.strategy && (
                            <p className="font-sans text-[13px] leading-[1.55] text-ink-500">
                              {fund.strategy}
                            </p>
                          )}
                          <div className="grid grid-cols-3 gap-4 border-t border-[color:var(--border-hairline)] pt-5">
                            <div className="flex flex-col gap-1">
                              <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                                Committed
                              </span>
                              <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                                {formatCurrency(committed, fund.currency_code, { compact: true })}
                              </span>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                                TVPI
                              </span>
                              <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                                {fund.tvpi ? `${tvpi.toFixed(2)}x` : "—"}
                              </span>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                                Net IRR
                              </span>
                              <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                                {fund.irr ? formatPercent(irr) : "—"}
                              </span>
                            </div>
                          </div>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between text-[11px] text-ink-500">
                              <span>Capital called</span>
                              <span className="es-numeric">
                                {formatPercent(calledPct)}
                              </span>
                            </div>
                            <ProgressBar value={calledPct} />
                          </div>
                        </CardSection>
                      </Card>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
