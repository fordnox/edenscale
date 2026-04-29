import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import { Stat } from "@/components/ui/stat"
import { StatusBadge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { distributions } from "@/data/mock"
import { formatCurrency, formatDate } from "@/lib/format"

export function DistributionsPage() {
  const total = distributions.reduce((acc, d) => acc + d.amount, 0)
  const ytd = distributions
    .filter((d) => d.distribution_date.startsWith("2026"))
    .reduce((acc, d) => acc + d.amount, 0)
  const upcoming = distributions.filter((d) =>
    ["scheduled", "sent"].includes(d.status),
  )

  return (
    <>
      <Topbar
        eyebrow="Distributions"
        title="Returns to limited partners."
        description="Cash and stock distributions, by fund and event."
        actions={
          <Button variant="primary" size="sm">Schedule distribution</Button>
        }
      />

      <div className="px-8 pb-16">
        <Card>
          <div className="grid grid-cols-1 md:grid-cols-3">
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Lifetime distributed"
                value={formatCurrency(total, "USD", { compact: true })}
                caption={`${distributions.length} events`}
              />
            </CardSection>
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="2026 year to date"
                value={formatCurrency(ytd, "USD", { compact: true })}
                trend="up"
                trendLabel="ahead of pacing"
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Upcoming"
                value={upcoming.length}
                caption={
                  upcoming.length > 0
                    ? `${formatCurrency(upcoming[0].amount, "USD", { compact: true })} on ${formatDate(upcoming[0].distribution_date)}`
                    : "Nothing scheduled"
                }
              />
            </CardSection>
          </div>
        </Card>

        <Card className="mt-8">
          <CardSection className="pt-2 pb-0">
            <DataTable>
              <thead>
                <tr>
                  <TH>Distribution</TH>
                  <TH>Fund</TH>
                  <TH align="right">Record date</TH>
                  <TH align="right">Distribution date</TH>
                  <TH align="right">Amount</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {distributions.map((d) => (
                  <TR key={d.id}>
                    <TD primary>{d.title}</TD>
                    <TD>{d.fund_name}</TD>
                    <TD align="right">{formatDate(d.record_date)}</TD>
                    <TD align="right">{formatDate(d.distribution_date)}</TD>
                    <TD align="right" primary>
                      {formatCurrency(d.amount, "USD", { compact: true })}
                    </TD>
                    <TD align="right">
                      <StatusBadge status={d.status} />
                    </TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          </CardSection>
        </Card>
      </div>
    </>
  )
}
