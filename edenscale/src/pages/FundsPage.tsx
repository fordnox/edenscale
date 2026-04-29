import { useState } from "react"
import { Topbar } from "@/components/layout/Topbar"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import { Card, CardSection } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/badge"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Button } from "@/components/ui/button"
import { ProgressBar } from "@/components/ui/progress"
import { funds, type FundStatus } from "@/data/mock"
import { formatCurrency, formatPercent } from "@/lib/format"

const filters: Array<{ id: "all" | FundStatus; label: string }> = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "liquidating", label: "Liquidating" },
  { id: "closed", label: "Closed" },
]

export function FundsPage({
  onSelect,
}: {
  onSelect: (id: number) => void
}) {
  const [filter, setFilter] = useState<(typeof filters)[number]["id"]>("all")
  const list = funds.filter((f) => filter === "all" || f.status === filter)

  return (
    <>
      <Topbar
        eyebrow="Programmes"
        title="Funds and vintages."
        description="A history of EdenScale capital. Each line is a fund, each fund a small list of holdings."
        actions={
          <>
            <Button variant="secondary" size="sm">Export PDF</Button>
            <Button variant="primary" size="sm">New fund</Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        <div className="mb-6 flex flex-wrap items-center gap-2">
          {filters.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={
                "rounded-xs border px-3.5 py-1.5 font-sans text-[12px] tracking-tight transition-colors " +
                (filter === f.id
                  ? "border-conifer-700 bg-conifer-700 text-parchment-50"
                  : "border-[color:var(--border-hairline)] bg-surface text-ink-700 hover:border-[color:var(--border-default)]")
              }
            >
              {f.label}
            </button>
          ))}
          <span className="ml-auto font-sans text-[12px] text-ink-500">
            {list.length} of {funds.length} programmes
          </span>
        </div>

        <Card>
          <CardSection className="pt-2 pb-0">
            <DataTable>
              <thead>
                <tr>
                  <TH>Fund</TH>
                  <TH>Strategy</TH>
                  <TH align="right">Vintage</TH>
                  <TH align="right">Committed</TH>
                  <TH align="right">Called</TH>
                  <TH align="right">DPI</TH>
                  <TH align="right">TVPI</TH>
                  <TH align="right">Net IRR</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {list.map((f) => {
                  const calledPct = f.committed > 0 ? f.called / f.committed : 0
                  return (
                    <TR
                      key={f.id}
                      className="cursor-pointer"
                      onClick={() => onSelect(f.id)}
                    >
                      <TD primary>
                        <div className="flex flex-col gap-1.5">
                          <span>{f.name}</span>
                          <span className="font-sans text-[11px] font-normal text-ink-500">
                            {f.legal_name}
                          </span>
                        </div>
                      </TD>
                      <TD>{f.strategy}</TD>
                      <TD align="right">{f.vintage_year}</TD>
                      <TD align="right" primary>
                        {formatCurrency(f.committed, f.currency_code, {
                          compact: true,
                        })}
                      </TD>
                      <TD align="right">
                        <div className="flex flex-col items-end gap-1.5">
                          <span className="es-numeric text-[13px] text-ink-900">
                            {formatPercent(calledPct)}
                          </span>
                          <ProgressBar
                            value={calledPct}
                            className="w-[72px]"
                          />
                        </div>
                      </TD>
                      <TD align="right">{f.dpi.toFixed(2)}x</TD>
                      <TD align="right">{f.tvpi.toFixed(2)}x</TD>
                      <TD align="right">{formatPercent(f.irr)}</TD>
                      <TD align="right">
                        <StatusBadge status={f.status} />
                      </TD>
                    </TR>
                  )
                })}
              </tbody>
            </DataTable>
          </CardSection>
        </Card>

        <p className="mt-6 max-w-2xl font-sans text-[12px] leading-[1.6] text-ink-500">
          Performance figures are net of management fees, carried interest and
          fund-level expenses, computed on a paid-in basis through 31 March 2026.
          Past performance is not indicative of future results.
        </p>

        <div className="mt-12">
          <div className="mb-6 flex items-end gap-4">
            <Eyebrow>Realized vintages</Eyebrow>
          </div>
          <Card raised>
            <CardSection>
              <p className="es-quote text-[26px] leading-[1.25]">
                "Eden Capital V closed in 2024 after twelve years. Final TVPI 2.91×.
                We will not raise a successor on the same strategy."
              </p>
              <p className="mt-5 font-sans text-[13px] text-ink-500">
                — Letter to limited partners, October 2024
              </p>
            </CardSection>
          </Card>
        </div>
      </div>
    </>
  )
}
