import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { ArrowLeft, Loader2 } from "lucide-react"

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

export default function FundDetailPage({
  fundId,
}: {
  fundId: string
  fundSlug: string
}) {
  const { activeMembership } = useActiveOrganization()
  const orgSlug = activeMembership?.organization.slug ?? null

  const fundQuery = useApiQuery("/funds/{fund_id}", {
    params: { path: { fund_id: fundId } },
  })
  const overviewQuery = useApiQuery("/funds/{fund_id}/overview", {
    params: { path: { fund_id: fundId } },
  })
  const commitmentsQuery = useApiQuery("/commitments", {
    params: { query: { fund_id: fundId } },
  })
  const callsQuery = useApiQuery("/capital-calls", {
    params: { query: { fund_id: fundId } },
  })
  const distributionsQuery = useApiQuery("/distributions", {
    params: { query: { fund_id: fundId } },
  })

  const fund = fundQuery.data
  const overview = overviewQuery.data
  const currency = fund?.currency_code ?? "USD"

  // The LP's personal position in this fund (summed across their commitments).
  const mine = useMemo(() => {
    let committed = 0
    let called = 0
    let distributed = 0
    for (const c of commitmentsQuery.data ?? []) {
      committed += parseDecimal(c.committed_amount)
      called += parseDecimal(c.called_amount)
      distributed += parseDecimal(c.distributed_amount)
    }
    // The LP's share of the fund NAV, pro-rated by their commitment.
    const fundNav = fund?.nav != null ? parseDecimal(fund.nav) : null
    const fundCommitted = parseDecimal(fund?.current_size)
    const fairValue =
      fundNav != null && fundCommitted > 0
        ? (committed / fundCommitted) * fundNav
        : null
    return {
      committed,
      called,
      distributed,
      dpi: called > 0 ? distributed / called : null,
      fairValue,
      tvpi:
        fairValue != null && called > 0
          ? (distributed + fairValue) / called
          : null,
    }
  }, [commitmentsQuery.data, fund?.nav, fund?.current_size])

  const calls = callsQuery.data ?? []
  const distributions = distributionsQuery.data ?? []

  return (
    <>
      <Helmet>
        <title>{`${fund?.name ?? "Fund"} · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow={
          fund?.vintage_year
            ? `Vintage ${fund.vintage_year} · ${currency}`
            : currency
        }
        title={fund?.name ?? "Fund"}
        description={fund?.strategy ?? undefined}
        actions={
          orgSlug ? (
            <Link
              to={orgPath(orgSlug, "funds")}
              className="inline-flex items-center gap-1.5 font-sans text-[13px] text-conifer-700 underline-offset-4 hover:underline"
            >
              <ArrowLeft strokeWidth={1.5} className="size-4" />
              All funds
            </Link>
          ) : undefined
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {fund?.status && (
          <div className="mb-6">
            <StatusPill kind="fund" value={fund.status} />
          </div>
        )}

        {/* Your position */}
        <Eyebrow>Your position</Eyebrow>
        <Card className="mt-4">
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Committed"
                value={formatCurrency(mine.committed, currency, { compact: true })}
              />
            </CardSection>
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Called"
                value={formatCurrency(mine.called, currency, { compact: true })}
                caption={
                  mine.committed > 0
                    ? `${Math.round((mine.called / mine.committed) * 100)}% of commitment`
                    : undefined
                }
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Distributed"
                value={formatCurrency(mine.distributed, currency, { compact: true })}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Your value"
                value={
                  mine.fairValue != null
                    ? formatCurrency(mine.fairValue, currency, { compact: true })
                    : mine.dpi != null
                      ? `${mine.dpi.toFixed(2)}×`
                      : "—"
                }
                caption={
                  mine.fairValue != null
                    ? mine.tvpi != null
                      ? `${mine.tvpi.toFixed(2)}× TVPI`
                      : "fair value"
                    : "DPI (no NAV yet)"
                }
              />
            </CardSection>
          </div>
        </Card>

        {/* Fund performance (fund-wide) */}
        <Eyebrow className="mt-10 block">Fund performance</Eyebrow>
        <Card className="mt-4">
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="Net IRR"
                value={
                  overview?.irr != null
                    ? formatPercent(parseDecimal(overview.irr))
                    : "—"
                }
              />
            </CardSection>
            <CardSection className="border-r border-b border-[color:var(--border-hairline)] md:border-b-0">
              <Stat
                label="DPI"
                value={
                  overview?.dpi != null
                    ? `${parseDecimal(overview.dpi).toFixed(2)}×`
                    : "—"
                }
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="TVPI"
                value={
                  overview?.tvpi != null
                    ? `${parseDecimal(overview.tvpi).toFixed(2)}×`
                    : "—"
                }
                caption={
                  overview?.rvpi != null
                    ? `${parseDecimal(overview.rvpi).toFixed(2)}× RVPI`
                    : undefined
                }
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Fund NAV"
                value={
                  overview?.nav != null
                    ? formatCurrency(parseDecimal(overview.nav), currency, {
                        compact: true,
                      })
                    : "—"
                }
                caption={
                  overview?.nav != null ? "fair value" : "not yet marked"
                }
              />
            </CardSection>
          </div>
        </Card>

        {/* Your capital calls */}
        <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
          <section>
            <Eyebrow>Your capital calls</Eyebrow>
            <Card className="mt-4">
              <CardSection className="pt-2 pb-0">
                {calls.length === 0 ? (
                  <EmptyState title="No capital calls" body="No calls for this fund yet." />
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
                      {calls.map((call) => {
                        const due = (call.items ?? []).reduce(
                          (acc, i) => acc + parseDecimal(i.amount_due),
                          0,
                        )
                        return (
                          <TR key={call.id}>
                            <TD primary>{call.title}</TD>
                            <TD align="right">{formatDate(call.due_date)}</TD>
                            <TD align="right">
                              {formatCurrency(due, currency, { compact: true })}
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
          </section>

          <section>
            <Eyebrow>Your distributions</Eyebrow>
            <Card className="mt-4">
              <CardSection className="pt-2 pb-0">
                {distributions.length === 0 ? (
                  <EmptyState
                    title="No distributions"
                    body="No distributions for this fund yet."
                  />
                ) : (
                  <DataTable>
                    <thead>
                      <tr>
                        <TH>Distribution</TH>
                        <TH align="right">Date</TH>
                        <TH align="right">Amount</TH>
                        <TH align="right">Status</TH>
                      </tr>
                    </thead>
                    <tbody>
                      {distributions.map((dist) => {
                        const due = (dist.items ?? []).reduce(
                          (acc, i) => acc + parseDecimal(i.amount_due),
                          0,
                        )
                        return (
                          <TR key={dist.id}>
                            <TD primary>{dist.title}</TD>
                            <TD align="right">
                              {formatDate(dist.distribution_date)}
                            </TD>
                            <TD align="right">
                              {formatCurrency(due, currency, { compact: true })}
                            </TD>
                            <TD align="right">
                              <StatusPill kind="distribution" value={dist.status} />
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
        </div>

        {(fundQuery.isLoading || overviewQuery.isLoading) && (
          <div className="mt-8 flex items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
          </div>
        )}
      </div>
    </>
  )
}
