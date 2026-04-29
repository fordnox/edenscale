import { ArrowUpRight, ArrowDownToLine, ArrowUpFromLine } from "lucide-react"
import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { Stat } from "@/components/ui/stat"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/badge"
import { ProgressBar } from "@/components/ui/progress"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import {
  capitalCalls,
  distributions,
  funds,
  getFirmAggregates,
  letters,
  tasks,
} from "@/data/mock"
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatRelativeDays,
} from "@/lib/format"
import type { Route } from "@/lib/router"

const TODAY = new Date("2026-04-29")

export function DashboardPage({ onNavigate }: { onNavigate: (r: Route) => void }) {
  const agg = getFirmAggregates()
  const upcoming = [
    ...capitalCalls
      .filter((c) => ["scheduled", "sent", "overdue"].includes(c.status))
      .map((c) => ({
        id: `c-${c.id}`,
        kind: "Capital call" as const,
        title: c.title,
        fund: c.fund_name,
        amount: c.amount,
        date: c.due_date,
        status: c.status,
      })),
    ...distributions
      .filter((d) => ["scheduled", "sent"].includes(d.status))
      .map((d) => ({
        id: `d-${d.id}`,
        kind: "Distribution" as const,
        title: d.title,
        fund: d.fund_name,
        amount: d.amount,
        date: d.distribution_date,
        status: d.status,
      })),
  ].sort((a, b) => a.date.localeCompare(b.date))

  const featuredLetter = letters[0]
  const openTasks = tasks.filter((t) => t.status !== "done").slice(0, 4)

  return (
    <>
      <Topbar
        eyebrow="Tuesday, 29 April 2026"
        title="Good morning, Margot."
        description="Across five funds, EdenScale is stewarding capital for sixty-three limited partners. Below is what needs attention this week."
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => onNavigate("calls")}>
              View capital calls
            </Button>
            <Button variant="primary" size="sm" onClick={() => onNavigate("letters")}>
              Draft quarterly letter
            </Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        {/* Aggregate KPIs */}
        <Card>
          <div className="grid grid-cols-1 gap-0 md:grid-cols-4">
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Total Committed"
                value={formatCurrency(agg.totalCommitted, "USD", { compact: true })}
                caption={`Across ${agg.fundCount} funds, ${agg.investorCount} limited partners`}
              />
            </CardSection>
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Capital Called"
                value={formatCurrency(agg.totalCalled, "USD", { compact: true })}
                caption={`${formatPercent(agg.totalCalled / agg.totalCommitted)} of commitments`}
              />
            </CardSection>
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Distributed"
                value={formatCurrency(agg.totalDistributed, "USD", { compact: true })}
                caption="Lifetime, across all vintages"
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Net Asset Value"
                value={formatCurrency(agg.totalNav, "USD", { compact: true })}
                trend="up"
                trendLabel="+4.2% qoq"
                caption={`Dry powder ${formatCurrency(agg.dryPowder, "USD", { compact: true })}`}
              />
            </CardSection>
          </div>
        </Card>

        {/* Two-column area: upcoming events + side rail */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
          <Card>
            <div className="flex items-end justify-between gap-4 px-6 pt-7 md:px-8 md:pt-8">
              <div className="flex flex-col gap-2">
                <Eyebrow>Upcoming</Eyebrow>
                <h2 className="es-display text-[28px]">
                  Capital activity, next four weeks.
                </h2>
              </div>
              <button
                className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700 transition-colors"
                onClick={() => onNavigate("calls")}
              >
                Open all →
              </button>
            </div>
            <CardSection className="pt-5">
              <DataTable>
                <thead>
                  <tr>
                    <TH>Event</TH>
                    <TH>Fund</TH>
                    <TH align="right">Amount</TH>
                    <TH align="right">Due</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {upcoming.slice(0, 6).map((e) => (
                    <TR key={e.id}>
                      <TD primary>
                        <div className="flex items-center gap-3">
                          <span
                            className={
                              "inline-flex size-7 shrink-0 items-center justify-center border " +
                              (e.kind === "Capital call"
                                ? "border-brass-500 text-brass-700"
                                : "border-conifer-600 text-conifer-700")
                            }
                          >
                            {e.kind === "Capital call" ? (
                              <ArrowDownToLine
                                strokeWidth={1.5}
                                className="size-3.5"
                              />
                            ) : (
                              <ArrowUpFromLine
                                strokeWidth={1.5}
                                className="size-3.5"
                              />
                            )}
                          </span>
                          <span className="leading-tight">{e.title}</span>
                        </div>
                      </TD>
                      <TD>{e.fund}</TD>
                      <TD align="right" primary>
                        {formatCurrency(e.amount, "USD", { compact: true })}
                      </TD>
                      <TD align="right">
                        <div className="flex flex-col items-end leading-tight">
                          <span className="text-ink-900 text-[14px]">
                            {formatDate(e.date)}
                          </span>
                          <span className="text-[11px] text-ink-500">
                            {formatRelativeDays(e.date, TODAY)}
                          </span>
                        </div>
                      </TD>
                      <TD align="right">
                        <StatusBadge status={e.status} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>
            </CardSection>
          </Card>

          {/* Side rail: featured letter + tasks */}
          <div className="flex flex-col gap-6">
            <Card raised>
              <CardSection>
                <Eyebrow>{featuredLetter.vol}</Eyebrow>
                <h3 className="es-display mt-4 text-[26px] leading-[1.15]">
                  {featuredLetter.subject}.
                </h3>
                <p className="mt-4 font-sans text-[14px] leading-[1.6] text-ink-700">
                  {featuredLetter.excerpt}
                </p>
                <div className="mt-5 flex items-center gap-3 text-[12px] text-ink-500">
                  <span>{formatDate(featuredLetter.sent_at)}</span>
                  <span className="size-1 rounded-full bg-ink-300" />
                  <span>{featuredLetter.read_minutes} min read</span>
                </div>
                <div className="mt-6">
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => onNavigate("letters")}
                  >
                    Open letter
                    <ArrowUpRight strokeWidth={1.5} className="size-4" />
                  </Button>
                </div>
              </CardSection>
            </Card>

            <Card>
              <div className="flex items-center justify-between px-6 pt-6 md:px-8 md:pt-7">
                <Eyebrow>To do</Eyebrow>
                <button
                  className="font-sans text-[12px] text-ink-500 hover:text-ink-900"
                  onClick={() => onNavigate("tasks")}
                >
                  All tasks →
                </button>
              </div>
              <ul className="mt-4 divide-y divide-[color:var(--border-hairline)]">
                {openTasks.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-start gap-3 px-6 py-4 md:px-8"
                  >
                    <span className="mt-1 inline-block size-2 shrink-0 rounded-full border border-conifer-600" />
                    <div className="flex flex-1 flex-col gap-1">
                      <span className="font-sans text-[14px] text-ink-900 leading-[1.4]">
                        {t.title}
                      </span>
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                        {t.fund_name && <span>{t.fund_name}</span>}
                        {t.fund_name && t.due_date && (
                          <span className="size-1 rounded-full bg-ink-300" />
                        )}
                        {t.due_date && (
                          <span>Due {formatDate(t.due_date)}</span>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={t.status} />
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>

        {/* Active funds */}
        <div className="mt-12">
          <div className="mb-6 flex items-end justify-between gap-4">
            <div className="flex flex-col gap-2">
              <Eyebrow>Active programmes</Eyebrow>
              <h2 className="es-display text-[32px]">
                Five funds, deliberately small.
              </h2>
            </div>
            <Button
              variant="link"
              size="sm"
              onClick={() => onNavigate("funds")}
            >
              All funds →
            </Button>
          </div>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            {funds
              .filter((f) => f.status !== "closed")
              .map((f) => {
                const calledPct = f.committed > 0 ? f.called / f.committed : 0
                return (
                  <Card key={f.id} className="flex flex-col">
                    <CardSection className="flex flex-1 flex-col gap-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex flex-col gap-1.5">
                          <Eyebrow>Vintage {f.vintage_year}</Eyebrow>
                          <h3 className="font-display text-[26px] font-medium leading-[1.1] tracking-[-0.015em] text-ink-900">
                            {f.name}
                          </h3>
                        </div>
                        <StatusBadge status={f.status} />
                      </div>
                      <p className="font-sans text-[13px] leading-[1.55] text-ink-500">
                        {f.strategy}
                      </p>
                      <div className="grid grid-cols-3 gap-4 border-t border-[color:var(--border-hairline)] pt-5">
                        <div className="flex flex-col gap-1">
                          <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                            Committed
                          </span>
                          <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                            {formatCurrency(f.committed, f.currency_code, {
                              compact: true,
                            })}
                          </span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                            TVPI
                          </span>
                          <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                            {f.tvpi.toFixed(2)}x
                          </span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                            Net IRR
                          </span>
                          <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                            {formatPercent(f.irr)}
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
        </div>
      </div>
    </>
  )
}
