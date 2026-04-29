import { ChevronLeft, Download } from "lucide-react"
import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { Stat } from "@/components/ui/stat"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/badge"
import { ProgressBar } from "@/components/ui/progress"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import {
  capitalCalls,
  commitments,
  distributions,
  documents,
  funds,
} from "@/data/mock"
import { formatCurrency, formatDate, formatPercent } from "@/lib/format"

export function FundDetailPage({
  fundId,
  onBack,
}: {
  fundId: number
  onBack: () => void
}) {
  const fund = funds.find((f) => f.id === fundId)
  if (!fund) {
    return (
      <div className="px-8 py-12">
        <Button variant="link" size="sm" onClick={onBack}>
          ← Back to funds
        </Button>
        <p className="mt-6 font-sans text-ink-700">Fund not found.</p>
      </div>
    )
  }

  const fundCommitments = commitments.filter((c) => c.fund_id === fund.id)
  const fundCalls = capitalCalls.filter((c) => c.fund_id === fund.id)
  const fundDistributions = distributions.filter((d) => d.fund_id === fund.id)
  const fundDocs = documents.filter((d) => d.fund_name === fund.name)
  const calledPct = fund.committed > 0 ? fund.called / fund.committed : 0

  return (
    <>
      <Topbar
        eyebrow={`Vintage ${fund.vintage_year} · ${fund.currency_code}`}
        title={fund.name}
        description={fund.description}
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={onBack}>
              <ChevronLeft strokeWidth={1.5} className="size-4" />
              All funds
            </Button>
            <Button variant="secondary" size="sm">
              <Download strokeWidth={1.5} className="size-4" />
              Quarterly report
            </Button>
            <Button variant="primary" size="sm">Issue capital call</Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <StatusBadge status={fund.status} />
          <span className="font-sans text-[13px] text-ink-500">
            {fund.legal_name}
          </span>
        </div>

        <Card className="mt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6">
            <CardSection className="border-r border-b lg:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Committed"
                value={formatCurrency(fund.committed, fund.currency_code, {
                  compact: true,
                })}
                caption={`${fund.investor_count} limited partners`}
              />
            </CardSection>
            <CardSection className="border-r border-b lg:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Called"
                value={formatCurrency(fund.called, fund.currency_code, {
                  compact: true,
                })}
                caption={`${formatPercent(calledPct)} of commitment`}
              />
            </CardSection>
            <CardSection className="border-b md:border-r lg:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Distributed"
                value={formatCurrency(fund.distributed, fund.currency_code, {
                  compact: true,
                })}
                caption="Lifetime"
              />
            </CardSection>
            <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="NAV"
                value={formatCurrency(fund.nav, fund.currency_code, {
                  compact: true,
                })}
                trend="up"
                trendLabel="+2.1% qoq"
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="TVPI"
                value={`${fund.tvpi.toFixed(2)}x`}
                caption={`DPI ${fund.dpi.toFixed(2)}x`}
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Net IRR"
                value={formatPercent(fund.irr)}
                trend="up"
                trendLabel="vs prior quarter"
              />
            </CardSection>
          </div>
        </Card>

        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
          <Card>
            <div className="flex items-end justify-between px-6 pt-7 md:px-8 md:pt-8">
              <div>
                <Eyebrow>Limited partners</Eyebrow>
                <h2 className="es-display mt-3 text-[28px]">
                  {fundCommitments.length} commitments to this fund.
                </h2>
              </div>
            </div>
            <CardSection className="pt-5">
              <DataTable>
                <thead>
                  <tr>
                    <TH>Investor</TH>
                    <TH align="right">Committed</TH>
                    <TH align="right">Called</TH>
                    <TH align="right">Distributed</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {fundCommitments.map((c) => (
                    <TR key={c.id}>
                      <TD primary>{c.investor_name}</TD>
                      <TD align="right" primary>
                        {formatCurrency(c.committed_amount, fund.currency_code, {
                          compact: true,
                        })}
                      </TD>
                      <TD align="right">
                        {formatCurrency(c.called_amount, fund.currency_code, {
                          compact: true,
                        })}
                      </TD>
                      <TD align="right">
                        {formatCurrency(
                          c.distributed_amount,
                          fund.currency_code,
                          { compact: true },
                        )}
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

          <div className="flex flex-col gap-6">
            <Card>
              <CardSection>
                <Eyebrow>Pacing</Eyebrow>
                <p className="mt-3 font-sans text-[14px] leading-[1.55] text-ink-700">
                  The fund has called {formatPercent(calledPct)} of committed
                  capital, on plan with a five-year deployment schedule.
                </p>
                <div className="mt-5 flex flex-col gap-2">
                  <div className="flex justify-between font-sans text-[12px] text-ink-500">
                    <span>Called</span>
                    <span className="es-numeric">
                      {formatCurrency(fund.called, fund.currency_code, {
                        compact: true,
                      })}{" "}
                      ·{" "}
                      {formatCurrency(fund.committed, fund.currency_code, {
                        compact: true,
                      })}
                    </span>
                  </div>
                  <ProgressBar value={calledPct} />
                </div>
                <div className="mt-5 flex flex-col gap-2">
                  <div className="flex justify-between font-sans text-[12px] text-ink-500">
                    <span>Distributed (DPI)</span>
                    <span className="es-numeric">{fund.dpi.toFixed(2)}×</span>
                  </div>
                  <ProgressBar
                    value={Math.min(1, fund.dpi / Math.max(fund.tvpi, 1))}
                    tone="brass"
                  />
                </div>
              </CardSection>
            </Card>

            <Card raised>
              <CardSection>
                <Eyebrow>Inception</Eyebrow>
                <p className="mt-3 font-sans text-[14px] leading-[1.55] text-ink-700">
                  Held since {formatDate(fund.inception_date)}. Fund operates in{" "}
                  {fund.currency_code} and is administered out of Luxembourg.
                </p>
              </CardSection>
            </Card>
          </div>
        </div>

        {/* Activity rows */}
        <div className="mt-12 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <div className="flex items-center justify-between px-6 pt-7 md:px-8 md:pt-8">
              <Eyebrow>Capital calls</Eyebrow>
              <span className="font-sans text-[12px] text-ink-500">
                {fundCalls.length} total
              </span>
            </div>
            <CardSection className="pt-4">
              <ul className="divide-y divide-[color:var(--border-hairline)]">
                {fundCalls.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"
                  >
                    <div className="flex flex-1 flex-col gap-1">
                      <span className="font-sans text-[14px] font-medium text-ink-900">
                        {c.title}
                      </span>
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                        <span>Due {formatDate(c.due_date)}</span>
                        <span className="size-1 rounded-full bg-ink-300" />
                        <span>
                          {formatCurrency(c.amount, fund.currency_code, {
                            compact: true,
                          })}
                        </span>
                      </div>
                    </div>
                    <StatusBadge status={c.status} />
                  </li>
                ))}
              </ul>
            </CardSection>
          </Card>

          <Card>
            <div className="flex items-center justify-between px-6 pt-7 md:px-8 md:pt-8">
              <Eyebrow>Distributions</Eyebrow>
              <span className="font-sans text-[12px] text-ink-500">
                {fundDistributions.length} total
              </span>
            </div>
            <CardSection className="pt-4">
              {fundDistributions.length === 0 ? (
                <p className="font-sans text-[13px] text-ink-500">
                  No distributions yet on this fund.
                </p>
              ) : (
                <ul className="divide-y divide-[color:var(--border-hairline)]">
                  {fundDistributions.map((d) => (
                    <li
                      key={d.id}
                      className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"
                    >
                      <div className="flex flex-1 flex-col gap-1">
                        <span className="font-sans text-[14px] font-medium text-ink-900">
                          {d.title}
                        </span>
                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                          <span>{formatDate(d.distribution_date)}</span>
                          <span className="size-1 rounded-full bg-ink-300" />
                          <span>
                            {formatCurrency(d.amount, fund.currency_code, {
                              compact: true,
                            })}
                          </span>
                        </div>
                      </div>
                      <StatusBadge status={d.status} />
                    </li>
                  ))}
                </ul>
              )}
            </CardSection>
          </Card>
        </div>

        {fundDocs.length > 0 && (
          <div className="mt-12">
            <div className="mb-5 flex items-end gap-3">
              <Eyebrow>Documents</Eyebrow>
              <span className="font-sans text-[12px] text-ink-500">
                {fundDocs.length} files
              </span>
            </div>
            <Card>
              <CardSection className="pt-2 pb-0">
                <DataTable>
                  <thead>
                    <tr>
                      <TH>Document</TH>
                      <TH>Type</TH>
                      <TH align="right">Uploaded</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {fundDocs.map((d) => (
                      <TR key={d.id}>
                        <TD primary>{d.title}</TD>
                        <TD className="capitalize">
                          {d.document_type.replace("_", " ")}
                        </TD>
                        <TD align="right">{formatDate(d.created_at)}</TD>
                      </TR>
                    ))}
                  </tbody>
                </DataTable>
              </CardSection>
            </Card>
          </div>
        )}
      </div>
    </>
  )
}
