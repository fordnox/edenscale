import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { FundCreateDialog } from "@/components/funds/FundCreateDialog"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { fundPath } from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatPercent } from "@edenscale/shared/format"
import { cn } from "@edenscale/shared/utils"
import type { components } from "@edenscale/api/schema"

type FundStatus = components["schemas"]["FundStatus"]
type FundListItem = components["schemas"]["FundListItem"]

const FILTERS: Array<{ id: "all" | FundStatus; label: string }> = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "liquidating", label: "Liquidating" },
  { id: "closed", label: "Closed" },
]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function formatMultiple(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return "—"
  const n = Number(value)
  return Number.isFinite(n) ? `${n.toFixed(2)}x` : "—"
}

function formatIrr(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return "—"
  const n = Number(value)
  return Number.isFinite(n) ? formatPercent(n) : "—"
}

export default function FundsPage() {
  const { activeMembership } = useActiveOrganization()
  const canCreateFund =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all")
  const [createOpen, setCreateOpen] = useState(false)
  const navigate = useNavigate()

  const { data, isLoading, isError } = useApiQuery("/funds")
  const groupsQuery = useApiQuery("/fund-groups")

  const funds = data ?? []
  const filtered = useMemo(
    () => (filter === "all" ? funds : funds.filter((f) => f.status === filter)),
    [funds, filter],
  )

  const hasGroups = useMemo(
    () => filtered.some((f) => f.fund_group_id),
    [filtered],
  )

  const groupedSections = useMemo(() => {
    const sections: Array<{ key: string; name: string; funds: FundListItem[] }> =
      []
    const placed = new Set<string>()
    for (const group of groupsQuery.data ?? []) {
      const groupFunds = filtered.filter((f) => f.fund_group_id === group.id)
      if (groupFunds.length > 0) {
        sections.push({ key: group.id, name: group.name, funds: groupFunds })
        for (const f of groupFunds) placed.add(f.id)
      }
    }
    // Everything not placed above lands in "Other funds" — including funds
    // whose group is unknown because /fund-groups is still loading or failed.
    // No fund may ever be dropped from the page.
    const leftover = filtered.filter((f) => !placed.has(f.id))
    if (leftover.length > 0) {
      sections.push({ key: "__other__", name: "Other funds", funds: leftover })
    }
    return sections
  }, [filtered, groupsQuery.data])

  const showEmptyState = !isLoading && !isError && funds.length === 0

  function renderFundsTable(list: FundListItem[]) {
    return (
      <Card>
        <CardSection className="pt-2 pb-0">
          <DataTable>
            <thead>
              <tr>
                <TH>Fund</TH>
                <TH align="right">Vintage</TH>
                <TH align="right">Target</TH>
                <TH align="right">Current</TH>
                <TH align="right">DPI</TH>
                <TH align="right">TVPI</TH>
                <TH align="right">Net IRR</TH>
                <TH align="right">Status</TH>
              </tr>
            </thead>
            <tbody>
              {list.map((fund) => {
                const target = parseDecimal(fund.target_size)
                const current = parseDecimal(fund.current_size)
                const calledPct = target > 0 ? Math.min(current / target, 1) : 0
                return (
                  <TR
                    key={fund.id}
                    className="cursor-pointer"
                    onClick={() => {
                      if (activeMembership) {
                        navigate(
                          fundPath(activeMembership.organization.slug, fund.slug),
                        )
                      }
                    }}
                  >
                    <TD primary>
                      <Link
                        to={
                          activeMembership
                            ? fundPath(activeMembership.organization.slug, fund.slug)
                            : "#"
                        }
                        onClick={(event) => event.stopPropagation()}
                        className="text-ink-900 hover:text-conifer-700"
                      >
                        {fund.name}
                      </Link>
                    </TD>
                    <TD align="right">{fund.vintage_year ?? "—"}</TD>
                    <TD align="right" primary>
                      {target > 0
                        ? formatCurrency(target, fund.currency_code, { compact: true })
                        : "—"}
                    </TD>
                    <TD align="right">
                      <div className="flex flex-col items-end gap-1.5">
                        <span className="es-numeric text-[13px] text-ink-900">
                          {target > 0
                            ? formatPercent(calledPct)
                            : formatCurrency(current, fund.currency_code, { compact: true })}
                        </span>
                        {target > 0 && (
                          <ProgressBar value={calledPct} className="w-[72px]" />
                        )}
                      </div>
                    </TD>
                    <TD align="right">{formatMultiple(fund.dpi)}</TD>
                    <TD align="right">{formatMultiple(fund.tvpi)}</TD>
                    <TD align="right">{formatIrr(fund.irr)}</TD>
                    <TD align="right">
                      <StatusPill kind="fund" value={fund.status} />
                    </TD>
                  </TR>
                )
              })}
            </tbody>
          </DataTable>
        </CardSection>
      </Card>
    )
  }

  return (
    <>
      <Helmet>
        <title>{`Funds · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Programmes"
        title="Funds and vintages."
        description="A history of NewTaven capital. Each line is a fund, each fund a small list of holdings."
        actions={
          canCreateFund && (
            <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
              New fund
            </Button>
          )
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {isLoading && (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        )}

        {isError && !isLoading && (
          <Card>
            <CardSection>
              <Eyebrow>Could not load funds</Eyebrow>
              <p className="mt-3 font-sans text-[14px] text-ink-700">
                We were unable to fetch your funds. Please refresh, or try again in a moment.
              </p>
            </CardSection>
          </Card>
        )}

        {showEmptyState && (
          <Card>
            <CardSection className="flex flex-col items-start gap-4">
              <Eyebrow>No funds yet</Eyebrow>
              <p className="max-w-xl font-sans text-[14px] leading-[1.6] text-ink-700">
                Once your organization sets up its first fund, it will appear here with committed and
                called capital figures.
              </p>
              {canCreateFund && (
                <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
                  New fund
                </Button>
              )}
            </CardSection>
          </Card>
        )}

        {!isLoading && !isError && funds.length > 0 && (
          <>
            <div className="mb-6 flex flex-wrap items-center gap-2">
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFilter(f.id)}
                  className={cn(
                    "rounded-xs border px-3.5 py-1.5 font-sans text-[12px] tracking-tight transition-colors",
                    filter === f.id
                      ? "border-conifer-700 bg-conifer-700 text-parchment-50"
                      : "border-[color:var(--border-hairline)] bg-surface text-ink-700 hover:border-[color:var(--border-default)]",
                  )}
                >
                  {f.label}
                </button>
              ))}
              <span className="ml-auto font-sans text-[12px] text-ink-500">
                {filtered.length} of {funds.length} programmes
              </span>
            </div>

            {filtered.length === 0 ? (
              <Card>
                <CardSection className="pt-2 pb-0">
                  <div className="flex flex-col items-start gap-2 py-8">
                    <Eyebrow>Nothing matches this filter</Eyebrow>
                    <p className="font-sans text-[14px] text-ink-700">
                      Try a different status to see other programmes.
                    </p>
                  </div>
                </CardSection>
              </Card>
            ) : hasGroups ? (
              <div className="flex flex-col gap-8">
                {groupedSections.map((section) => (
                  <div key={section.key} className="flex flex-col gap-3">
                    <Eyebrow>{section.name}</Eyebrow>
                    {renderFundsTable(section.funds)}
                  </div>
                ))}
              </div>
            ) : (
              renderFundsTable(filtered)
            )}
          </>
        )}
      </div>

      <FundCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </>
  )
}
