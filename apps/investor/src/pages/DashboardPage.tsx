import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Stat } from "@edenscale/ui/stat"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { UpdatesFeed } from "@/components/UpdatesFeed"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { fundPath } from "@/lib/investorRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatPercent } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function metric(value: string | null | undefined, currency = "USD") {
  return formatCurrency(parseDecimal(value), currency, { compact: true })
}

interface Position {
  fundId: string
  fundName: string
  fundSlug: string | null
  currency: string
  committed: number
  paidIn: number
  distributed: number
  unfunded: number
  fairValue: number | null
  tvpi: number | null
  irr: number | null
}

function money(value: number, currency: string) {
  return formatCurrency(value, currency, { compact: false })
}

export default function DashboardPage() {
  const { activeOrganization } = useInvestorOrganizations()
  const orgSlug = activeOrganization?.organization.slug ?? null

  const fundsQuery = useApiQuery("/investor/funds")
  const fundSlugById = useMemo(
    () => new Map((fundsQuery.data ?? []).map((f) => [f.id, f.slug])),
    [fundsQuery.data],
  )
  // Fund-wide NAV and total committed (current_size) — used to derive the LP's
  // share of fund fair value: LP NAV = (LP committed / fund committed) × NAV.
  const fundMetaById = useMemo(
    () =>
      new Map(
        (fundsQuery.data ?? []).map((f) => [
          f.id,
          {
            nav: f.nav != null ? parseDecimal(f.nav) : null,
            totalCommitted: parseDecimal(f.current_size),
          },
        ]),
      ),
    [fundsQuery.data],
  )

  const commitmentsQuery = useApiQuery("/investor/commitments")
  const overviewQuery = useApiQuery("/investor/dashboard/overview", undefined, {
    enabled: Boolean(activeOrganization?.organization_id),
  })
  const data = overviewQuery.data

  // Fund-wide IRR is only surfaced through the dashboard's recent_funds.
  const irrByFund = useMemo(() => {
    const map = new Map<string, number | null>()
    for (const f of data?.recent_funds ?? []) {
      map.set(f.id, f.irr != null ? parseDecimal(f.irr) : null)
    }
    return map
  }, [data?.recent_funds])

  // The LP's consolidated position, one row per fund (summed across their
  // commitments in that fund) plus a Total. Fair Value is the LP's share of the
  // fund NAV; TVPI = (their distributed + their fair value) / their paid-in.
  const positions = useMemo<Position[]>(() => {
    const byFund = new Map<
      string,
      Omit<Position, "fairValue" | "tvpi">
    >()
    for (const c of commitmentsQuery.data ?? []) {
      const existing = byFund.get(c.fund_id)
      const committed = parseDecimal(c.committed_amount)
      const paidIn = parseDecimal(c.called_amount)
      const distributed = parseDecimal(c.distributed_amount)
      if (existing) {
        existing.committed += committed
        existing.paidIn += paidIn
        existing.distributed += distributed
        existing.unfunded = existing.committed - existing.paidIn
      } else {
        byFund.set(c.fund_id, {
          fundId: c.fund_id,
          fundName: c.fund.name,
          fundSlug: fundSlugById.get(c.fund_id) ?? null,
          currency: c.fund.currency_code,
          committed,
          paidIn,
          distributed,
          unfunded: committed - paidIn,
          irr: irrByFund.get(c.fund_id) ?? null,
        })
      }
    }
    return [...byFund.values()]
      .map((p): Position => {
        const meta = fundMetaById.get(p.fundId)
        const fairValue =
          meta?.nav != null && meta.totalCommitted > 0
            ? (p.committed / meta.totalCommitted) * meta.nav
            : null
        const tvpi =
          fairValue != null && p.paidIn > 0
            ? (p.distributed + fairValue) / p.paidIn
            : null
        return { ...p, fairValue, tvpi }
      })
      .sort((a, b) => b.committed - a.committed)
  }, [commitmentsQuery.data, fundSlugById, irrByFund, fundMetaById])

  const totals = useMemo(() => {
    return positions.reduce(
      (acc, p) => ({
        committed: acc.committed + p.committed,
        paidIn: acc.paidIn + p.paidIn,
        distributed: acc.distributed + p.distributed,
        unfunded: acc.unfunded + p.unfunded,
        fairValue: acc.fairValue + (p.fairValue ?? 0),
      }),
      { committed: 0, paidIn: 0, distributed: 0, unfunded: 0, fairValue: 0 },
    )
  }, [positions])

  // A single reporting currency for the Total row only makes sense when every
  // position shares one; otherwise the per-row currencies are what's exact.
  const totalCurrency = useMemo(() => {
    const set = new Set(positions.map((p) => p.currency))
    return set.size === 1 ? [...set][0] : null
  }, [positions])

  const loading = commitmentsQuery.isLoading || overviewQuery.isLoading

  return (
    <>
      <Helmet>
        <title>{`Overview · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Investor portal"
        title={activeOrganization?.organization.name ?? "Portfolio overview"}
        description="Your positions, capital activity, and correspondence across the funds you hold. Figures are your share of each fund."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {/* Consolidated position table */}
        <Card>
          <CardSection className="pt-2 pb-0">
            {loading ? (
              <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : positions.length === 0 ? (
              <EmptyState
                title="No positions"
                body="You do not hold commitments in any fund yet."
              />
            ) : (
              <div className="overflow-x-auto">
                <DataTable>
                  <thead>
                    <tr>
                      <TH>Fund</TH>
                      <TH align="right">Commitment</TH>
                      <TH align="right">Paid-in</TH>
                      <TH align="right">Distributed</TH>
                      <TH align="right">Unfunded</TH>
                      <TH align="right">Fair value</TH>
                      <TH align="right">TVPI</TH>
                      <TH align="right">Net IRR</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => (
                      <TR key={p.fundId}>
                        <TD primary>
                          {p.fundSlug && orgSlug ? (
                            <Link to={fundPath(orgSlug, p.fundSlug)}>
                              {p.fundName}
                            </Link>
                          ) : (
                            p.fundName
                          )}
                          <span className="ml-2 font-sans text-[11px] text-ink-500">
                            {p.currency}
                          </span>
                        </TD>
                        <TD align="right">{money(p.committed, p.currency)}</TD>
                        <TD align="right">{money(p.paidIn, p.currency)}</TD>
                        <TD align="right">
                          {p.distributed > 0
                            ? `(${money(p.distributed, p.currency)})`
                            : money(0, p.currency)}
                        </TD>
                        <TD align="right">{money(p.unfunded, p.currency)}</TD>
                        <TD align="right">
                          {p.fairValue != null
                            ? money(p.fairValue, p.currency)
                            : "—"}
                        </TD>
                        <TD align="right">
                          {p.tvpi != null ? `${p.tvpi.toFixed(2)}×` : "—"}
                        </TD>
                        <TD align="right">
                          {p.irr != null ? formatPercent(p.irr) : "—"}
                        </TD>
                      </TR>
                    ))}
                    <TR>
                      <TD primary>Total</TD>
                      <TD align="right" primary>
                        {totalCurrency
                          ? money(totals.committed, totalCurrency)
                          : "—"}
                      </TD>
                      <TD align="right" primary>
                        {totalCurrency ? money(totals.paidIn, totalCurrency) : "—"}
                      </TD>
                      <TD align="right" primary>
                        {totalCurrency
                          ? totals.distributed > 0
                            ? `(${money(totals.distributed, totalCurrency)})`
                            : money(0, totalCurrency)
                          : "—"}
                      </TD>
                      <TD align="right" primary>
                        {totalCurrency
                          ? money(totals.unfunded, totalCurrency)
                          : "—"}
                      </TD>
                      <TD align="right" primary>
                        {totalCurrency && totals.fairValue > 0
                          ? money(totals.fairValue, totalCurrency)
                          : "—"}
                      </TD>
                      <TD align="right" />
                      <TD align="right" />
                    </TR>
                  </tbody>
                </DataTable>
              </div>
            )}
          </CardSection>
        </Card>

        {/* Quick figures */}
        <Card className="mt-8">
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
                trend={(data?.capital_calls_outstanding ?? 0) > 0 ? "down" : "flat"}
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

        {/* Unified activity timeline */}
        <div className="mt-8">
          <UpdatesFeed orgSlug={orgSlug} archiveLink />
        </div>
      </div>
    </>
  )
}
