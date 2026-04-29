import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import { Stat } from "@/components/ui/stat"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { investors } from "@/data/mock"
import { formatCurrency } from "@/lib/format"

export function InvestorsPage() {
  const totalCommitted = investors.reduce((acc, i) => acc + i.total_committed, 0)
  const accreditedCount = investors.filter((i) => i.accredited).length
  const regions = new Set(investors.map((i) => i.region)).size

  return (
    <>
      <Topbar
        eyebrow="Limited partners"
        title="Investors and commitments."
        description="A small register, kept by hand. We add new partners by referral, and only when an existing allocation closes."
        actions={
          <>
            <Button variant="secondary" size="sm">Export CSV</Button>
            <Button variant="primary" size="sm">Invite investor</Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        <Card>
          <div className="grid grid-cols-1 md:grid-cols-3">
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Investors on register"
                value={investors.length}
                caption={`${accreditedCount} accredited · ${regions} jurisdictions`}
              />
            </CardSection>
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Aggregate commitments"
                value={formatCurrency(totalCommitted, "USD", { compact: true })}
                caption="Lifetime, across all programmes"
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Average position"
                value={formatCurrency(totalCommitted / investors.length, "USD", {
                  compact: true,
                })}
                caption="Mean commitment per investor"
              />
            </CardSection>
          </div>
        </Card>

        <Card className="mt-8">
          <CardSection className="pt-2 pb-0">
            <DataTable>
              <thead>
                <tr>
                  <TH>Investor</TH>
                  <TH>Type</TH>
                  <TH>Primary contact</TH>
                  <TH>Region</TH>
                  <TH align="right">Active funds</TH>
                  <TH align="right">Total committed</TH>
                </tr>
              </thead>
              <tbody>
                {investors.map((inv) => (
                  <TR key={inv.id}>
                    <TD primary>
                      <div className="flex flex-col gap-1">
                        <span>{inv.name}</span>
                        <span className="font-sans text-[11px] font-normal text-ink-500">
                          {inv.investor_code}
                        </span>
                      </div>
                    </TD>
                    <TD>{inv.investor_type}</TD>
                    <TD>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-ink-900">{inv.primary_contact}</span>
                        <span className="font-sans text-[11px] text-ink-500">
                          {inv.primary_email}
                        </span>
                      </div>
                    </TD>
                    <TD>{inv.region}</TD>
                    <TD align="right">{inv.active_funds}</TD>
                    <TD align="right" primary>
                      {formatCurrency(inv.total_committed, "USD", {
                        compact: true,
                      })}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          </CardSection>
        </Card>

        <p className="mt-6 max-w-2xl font-sans text-[12px] leading-[1.6] text-ink-500">
          Identity and address details are redacted. To view full KYC packets,
          open the investor record. <Badge tone="info">Compliance</Badge>
        </p>
      </div>
    </>
  )
}
