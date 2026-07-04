import { useNavigate } from "react-router-dom"
import { Layers } from "lucide-react"

import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { formatCurrency, formatPercent } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type FundSummary = components["schemas"]["FundSummary"]

export interface FundsListItem {
  fund: FundSummary
  /** Where clicking the row navigates (the owning org's funds page). */
  to: string
}

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

interface FundsListCardProps {
  funds: FundsListItem[]
}

// Takes the onboarding card's slot on the dashboards once setup is complete:
// a compact roster of funds with committed capital and called progress.
export function FundsListCard({ funds }: FundsListCardProps) {
  const navigate = useNavigate()

  return (
    <Card>
      <div className="flex flex-col gap-2 px-6 pt-7 md:px-8 md:pt-8">
        <Eyebrow>Funds</Eyebrow>
        <h2 className="es-display text-[28px]">Core setup is complete.</h2>
        <p className="max-w-2xl font-sans text-[14px] leading-[1.6] text-ink-700">
          Every onboarding step is done. Keep the register, calls, and letters
          current as activity develops — your funds at a glance:
        </p>
      </div>

      <CardSection className="pt-6">
        {funds.length === 0 ? (
          <div className="flex flex-col items-start gap-2 py-6">
            <Eyebrow>No funds visible</Eyebrow>
            <p className="font-sans text-[14px] text-ink-700">
              Funds will appear here with committed and called capital figures.
            </p>
          </div>
        ) : (
          <div className="flex flex-col border-y border-[color:var(--border-hairline)]">
            {funds.map(({ fund, to }) => {
              const committed = parseDecimal(fund.committed_amount)
              const called = parseDecimal(fund.called_amount)
              const calledPct = committed > 0 ? called / committed : 0
              return (
                <button
                  key={fund.id}
                  type="button"
                  onClick={() => navigate(to)}
                  className="group flex items-center gap-4 border-b border-[color:var(--border-hairline)] py-4 text-left transition-colors duration-[140ms] last:border-b-0 hover:bg-parchment-100"
                >
                  <span className="inline-flex size-10 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
                    <Layers strokeWidth={1.5} className="size-4" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate font-sans text-[14px] font-semibold text-ink-900 group-hover:text-conifer-700">
                      {fund.name}
                    </span>
                    <span className="font-sans text-[11px] uppercase tracking-[0.08em] text-ink-500">
                      {fund.vintage_year ? `Vintage ${fund.vintage_year}` : "—"}
                      {fund.strategy ? ` · ${fund.strategy}` : ""}
                    </span>
                  </span>
                  <span className="hidden w-40 shrink-0 flex-col gap-1.5 sm:flex">
                    <span className="flex items-center justify-between font-sans text-[11px] text-ink-500">
                      <span>Called</span>
                      <span className="es-numeric">{formatPercent(calledPct)}</span>
                    </span>
                    <ProgressBar value={calledPct} />
                  </span>
                  <span className="es-numeric hidden shrink-0 font-sans text-[14px] font-semibold text-ink-900 md:inline">
                    {formatCurrency(committed, fund.currency_code, {
                      compact: true,
                    })}
                  </span>
                  <StatusPill kind="fund" value={fund.status} />
                </button>
              )
            })}
          </div>
        )}
      </CardSection>
    </Card>
  )
}
