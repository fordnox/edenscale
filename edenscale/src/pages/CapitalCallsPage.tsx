import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import { Stat } from "@/components/ui/stat"
import { StatusBadge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ProgressBar } from "@/components/ui/progress"
import { capitalCalls } from "@/data/mock"
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatRelativeDays,
} from "@/lib/format"

const TODAY = new Date("2026-04-29")

export function CapitalCallsPage() {
  const open = capitalCalls.filter((c) =>
    ["scheduled", "sent", "partially_paid", "overdue"].includes(c.status),
  )
  const overdue = capitalCalls.filter((c) => c.status === "overdue")
  const callTotal = capitalCalls.reduce((acc, c) => acc + c.amount, 0)
  const openTotal = open.reduce((acc, c) => acc + c.amount, 0)

  return (
    <>
      <Topbar
        eyebrow="Capital calls"
        title="What we have called, and what awaits."
        description="Drawdowns issued across funds. Status updates as wires settle."
        actions={
          <>
            <Button variant="secondary" size="sm">Export</Button>
            <Button variant="primary" size="sm">New capital call</Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Open calls"
                value={open.length}
                caption={`${formatCurrency(openTotal, "USD", { compact: true })} outstanding`}
              />
            </CardSection>
            <CardSection className="border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Overdue"
                value={overdue.length}
                trend={overdue.length > 0 ? "down" : "flat"}
                trendLabel={overdue.length > 0 ? "needs attention" : "all current"}
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Lifetime called"
                value={formatCurrency(callTotal, "USD", { compact: true })}
                caption={`${capitalCalls.length} calls issued`}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Avg paid in"
                value="9 days"
                caption="From notice to wire"
              />
            </CardSection>
          </div>
        </Card>

        <div className="mt-8">
          <Card>
            <CardSection className="pt-2 pb-0">
              <DataTable>
                <thead>
                  <tr>
                    <TH>Call</TH>
                    <TH>Fund</TH>
                    <TH align="right">Amount</TH>
                    <TH align="right">Notice</TH>
                    <TH align="right">Due</TH>
                    <TH align="right">Paid</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {capitalCalls.map((c) => (
                    <TR key={c.id}>
                      <TD primary>
                        <div className="flex flex-col gap-1">
                          <span>{c.title}</span>
                          <span className="font-sans text-[11px] font-normal text-ink-500">
                            {c.investor_count} limited partners
                          </span>
                        </div>
                      </TD>
                      <TD>{c.fund_name}</TD>
                      <TD align="right" primary>
                        {formatCurrency(c.amount, "USD", { compact: true })}
                      </TD>
                      <TD align="right">{formatDate(c.call_date)}</TD>
                      <TD align="right">
                        <div className="flex flex-col items-end leading-tight">
                          <span className="text-ink-900 text-[14px]">
                            {formatDate(c.due_date)}
                          </span>
                          <span className="text-[11px] text-ink-500">
                            {formatRelativeDays(c.due_date, TODAY)}
                          </span>
                        </div>
                      </TD>
                      <TD align="right">
                        <div className="flex flex-col items-end gap-1.5">
                          <span className="es-numeric text-[13px] text-ink-900">
                            {formatPercent(c.paid_pct)}
                          </span>
                          <ProgressBar
                            value={c.paid_pct}
                            className="w-[80px]"
                            tone={
                              c.status === "overdue" ? "brass" : "brand"
                            }
                          />
                        </div>
                      </TD>
                      <TD align="right">
                        <StatusBadge status={c.status} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>
            </CardSection>
          </Card>
        </div>
      </div>
    </>
  )
}
