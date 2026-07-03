import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { fundPath } from "@/lib/investorRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function FundsPage() {
  const { activeMembership } = useActiveOrganization()
  const orgSlug = activeMembership?.organization.slug ?? null

  const fundsQuery = useApiQuery("/funds")
  const commitmentsQuery = useApiQuery("/commitments")

  const committedByFund = useMemo(() => {
    const map = new Map<string, number>()
    for (const c of commitmentsQuery.data ?? []) {
      map.set(c.fund_id, (map.get(c.fund_id) ?? 0) + parseDecimal(c.committed_amount))
    }
    return map
  }, [commitmentsQuery.data])

  const funds = fundsQuery.data ?? []

  return (
    <>
      <Helmet>
        <title>{`Funds · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Programmes"
        title="Funds you hold."
        description="The funds you are committed to. Open one to review your commitment, capital calls, and distributions."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          <CardSection className="pt-2 pb-0">
            {fundsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : funds.length === 0 ? (
              <EmptyState
                title="No funds"
                body="You do not hold commitments in any fund yet. Once a commitment is recorded, the fund will appear here."
              />
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Fund</TH>
                    <TH align="right">Vintage</TH>
                    <TH align="right">Your commitment</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {funds.map((fund) => (
                    <TR key={fund.id}>
                      <TD primary>
                        {orgSlug ? (
                          <Link to={fundPath(orgSlug, fund.slug)}>{fund.name}</Link>
                        ) : (
                          fund.name
                        )}
                      </TD>
                      <TD align="right">{fund.vintage_year ?? "—"}</TD>
                      <TD align="right" primary>
                        {committedByFund.has(fund.id)
                          ? formatCurrency(
                              committedByFund.get(fund.id) ?? 0,
                              fund.currency_code,
                              { compact: true },
                            )
                          : "—"}
                      </TD>
                      <TD align="right">
                        <StatusPill kind="fund" value={fund.status} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>
            )}
          </CardSection>
        </Card>
      </div>
    </>
  )
}
