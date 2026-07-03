import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { orgPath } from "@/lib/investorRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatDate, formatPercent } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function metric(value: string | null | undefined, currency = "USD") {
  return formatCurrency(parseDecimal(value), currency, { compact: true })
}

export default function DashboardPage() {
  const { activeMembership } = useActiveOrganization()
  const orgSlug = activeMembership?.organization.slug ?? null

  const fundsQuery = useApiQuery("/funds")
  const fundSlugById = useMemo(
    () => new Map((fundsQuery.data ?? []).map((f) => [f.id, f.slug])),
    [fundsQuery.data],
  )

  const overviewQuery = useApiQuery("/dashboard/overview", undefined, {
    enabled: Boolean(activeMembership?.organization_id),
  })
  const data = overviewQuery.data

  return (
    <>
      <Helmet>
        <title>{`Overview · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Investor portal"
        title={activeMembership?.organization.name ?? "Portfolio overview"}
        description="Your commitments, capital activity, and correspondence across the funds you hold."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {overviewQuery.isLoading ? (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : (
          <>
            <Card>
              <div className="grid grid-cols-2 md:grid-cols-4">
                <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
                  <Stat
                    label="Committed"
                    value={metric(data?.commitments_total_amount)}
                    caption={`${data?.funds_active ?? 0} active funds`}
                  />
                </CardSection>
                <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
                  <Stat
                    label="Outstanding calls"
                    value={data?.capital_calls_outstanding ?? 0}
                    trend={
                      (data?.capital_calls_outstanding ?? 0) > 0 ? "down" : "flat"
                    }
                    trendLabel={
                      (data?.capital_calls_outstanding ?? 0) > 0
                        ? "awaiting funding"
                        : "all funded"
                    }
                  />
                </CardSection>
                <CardSection className="border-r border-[color:var(--border-hairline)]">
                  <Stat
                    label="Distributions YTD"
                    value={metric(data?.distributions_ytd_amount)}
                  />
                </CardSection>
                <CardSection>
                  <Stat
                    label="Unread"
                    value={data?.unread_notifications_count ?? 0}
                    caption="notifications"
                  />
                </CardSection>
              </div>
            </Card>

            <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
              <section>
                <div className="mb-4 flex items-end justify-between">
                  <Eyebrow>Your funds</Eyebrow>
                  {orgSlug && (
                    <Link
                      to={orgPath(orgSlug, "funds")}
                      className="font-sans text-[12px] text-conifer-700 underline-offset-4 hover:underline"
                    >
                      All funds
                    </Link>
                  )}
                </div>
                <Card>
                  <CardSection className="pt-2 pb-0">
                    {(data?.recent_funds ?? []).length === 0 ? (
                      <EmptyState title="No funds" body="You do not hold commitments in any fund yet." />
                    ) : (
                      <DataTable>
                        <thead>
                          <tr>
                            <TH>Fund</TH>
                            <TH align="right">Committed</TH>
                            <TH align="right">Called</TH>
                            <TH align="right">DPI</TH>
                            <TH align="right">Net IRR</TH>
                          </tr>
                        </thead>
                        <tbody>
                          {(data?.recent_funds ?? []).map((fund) => {
                            const slug = fundSlugById.get(fund.id)
                            return (
                              <TR key={fund.id}>
                                <TD primary>
                                  {slug && orgSlug ? (
                                    <Link to={`/investor/${orgSlug}/${slug}`}>
                                      {fund.name}
                                    </Link>
                                  ) : (
                                    fund.name
                                  )}
                                </TD>
                                <TD align="right">
                                  {formatCurrency(
                                    parseDecimal(fund.committed_amount),
                                    fund.currency_code,
                                    { compact: true },
                                  )}
                                </TD>
                                <TD align="right">
                                  {formatCurrency(
                                    parseDecimal(fund.called_amount),
                                    fund.currency_code,
                                    { compact: true },
                                  )}
                                </TD>
                                <TD align="right">
                                  {fund.dpi != null
                                    ? `${parseDecimal(fund.dpi).toFixed(2)}×`
                                    : "—"}
                                </TD>
                                <TD align="right">
                                  {fund.irr != null
                                    ? formatPercent(parseDecimal(fund.irr))
                                    : "—"}
                                </TD>
                              </TR>
                            )
                          })}
                        </tbody>
                      </DataTable>
                    )}
                  </CardSection>
                </Card>
              </section>

              <section>
                <div className="mb-4 flex items-end justify-between">
                  <Eyebrow>Upcoming capital calls</Eyebrow>
                  {orgSlug && (
                    <Link
                      to={orgPath(orgSlug, "calls")}
                      className="font-sans text-[12px] text-conifer-700 underline-offset-4 hover:underline"
                    >
                      All calls
                    </Link>
                  )}
                </div>
                <Card>
                  <CardSection className="pt-2 pb-0">
                    {(data?.upcoming_capital_calls ?? []).length === 0 ? (
                      <EmptyState title="Nothing due" body="You have no upcoming capital calls." />
                    ) : (
                      <DataTable>
                        <thead>
                          <tr>
                            <TH>Call</TH>
                            <TH align="right">Due</TH>
                            <TH align="right">Amount</TH>
                            <TH align="right">Status</TH>
                          </tr>
                        </thead>
                        <tbody>
                          {(data?.upcoming_capital_calls ?? []).map((call) => (
                            <TR key={call.id}>
                              <TD primary>
                                <div className="flex flex-col gap-1">
                                  <span>{call.title}</span>
                                  <span className="font-sans text-[11px] font-normal text-ink-500">
                                    {call.fund_name}
                                  </span>
                                </div>
                              </TD>
                              <TD align="right">{formatDate(call.due_date)}</TD>
                              <TD align="right" primary>
                                {formatCurrency(parseDecimal(call.amount), "USD", {
                                  compact: true,
                                })}
                              </TD>
                              <TD align="right">
                                <StatusPill kind="capital_call" value={call.status} />
                              </TD>
                            </TR>
                          ))}
                        </tbody>
                      </DataTable>
                    )}
                  </CardSection>
                </Card>
              </section>
            </div>
          </>
        )}
      </div>
    </>
  )
}
