import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams, useNavigate } from "react-router-dom"
import { ChevronLeft, Loader2 } from "lucide-react"

import { PageHero } from "@/components/layout/PageHero"
import { FundEditDialog } from "@/components/funds/FundEditDialog"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { ProgressBar } from "@/components/ui/progress"
import { Stat } from "@/components/ui/stat"
import { StatusPill } from "@/components/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import {
  formatCurrency,
  formatDate,
  formatDateLong,
  formatPercent,
  titleCase,
} from "@/lib/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function FundDetailPageContent({ fundId }: { fundId: number }) {
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)

  const fundQuery = useApiQuery("/funds/{fund_id}", {
    params: { path: { fund_id: fundId } },
  })
  const overviewQuery = useApiQuery("/funds/{fund_id}/overview", {
    params: { path: { fund_id: fundId } },
  })
  const commitmentsQuery = useApiQuery("/funds/{fund_id}/commitments", {
    params: { path: { fund_id: fundId } },
  })
  const callsQuery = useApiQuery("/funds/{fund_id}/capital-calls", {
    params: { path: { fund_id: fundId } },
  })
  const distributionsQuery = useApiQuery("/funds/{fund_id}/distributions", {
    params: { path: { fund_id: fundId } },
  })
  const teamQuery = useApiQuery("/funds/{fund_id}/team", {
    params: { path: { fund_id: fundId } },
  })
  const lettersQuery = useApiQuery("/funds/{fund_id}/communications", {
    params: { path: { fund_id: fundId }, query: { limit: 5 } },
  })

  if (fundQuery.isLoading || overviewQuery.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  if (fundQuery.isError || !fundQuery.data) {
    return (
      <>
        <PageHero
          eyebrow="Programmes"
          title="Fund not found."
          description="We were unable to load this fund. It may have been archived or the link is incorrect."
          actions={
            <Button variant="secondary" size="sm" onClick={() => navigate("/funds")}>
              <ChevronLeft strokeWidth={1.5} className="size-4" />
              All funds
            </Button>
          }
        />
      </>
    )
  }

  const fund = fundQuery.data
  const overview = overviewQuery.data
  const commitments = commitmentsQuery.data ?? []
  const calls = callsQuery.data ?? []
  const distributions = distributionsQuery.data ?? []
  const team = teamQuery.data ?? []
  const letters = lettersQuery.data ?? []

  const committed = parseDecimal(overview?.committed)
  const called = parseDecimal(overview?.called)
  const distributed = parseDecimal(overview?.distributed)
  const remaining = parseDecimal(overview?.remaining_commitment)
  const calledPct = committed > 0 ? called / committed : 0
  const targetSize = parseDecimal(fund.target_size)
  const targetPct = targetSize > 0 ? Math.min(committed / targetSize, 1) : 0
  const eyebrowParts = [
    fund.vintage_year ? `Vintage ${fund.vintage_year}` : null,
    fund.currency_code,
  ].filter((part): part is string => Boolean(part))

  return (
    <>
      <Helmet>
        <title>{`${fund.name} · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>

      <PageHero
        eyebrow={eyebrowParts.join(" · ")}
        title={fund.name}
        description={fund.description ?? undefined}
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => navigate("/funds")}>
              <ChevronLeft strokeWidth={1.5} className="size-4" />
              All funds
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>
              Edit fund
            </Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <StatusPill kind="fund" value={fund.status} />
          {fund.legal_name && (
            <span className="font-sans text-[13px] text-ink-500">
              {fund.legal_name}
            </span>
          )}
          {fund.strategy && (
            <span className="font-sans text-[13px] text-ink-500">
              {fund.strategy}
            </span>
          )}
        </div>

        {/* KPI strip */}
        <Card className="mt-6">
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Committed"
                value={formatCurrency(committed, fund.currency_code, { compact: true })}
                caption={
                  targetSize > 0
                    ? `${formatPercent(targetPct)} of ${formatCurrency(targetSize, fund.currency_code, { compact: true })} target`
                    : `${commitments.length} commitments`
                }
              />
            </CardSection>
            <CardSection className="border-b md:border-r md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Called"
                value={formatCurrency(called, fund.currency_code, { compact: true })}
                caption={
                  committed > 0 ? `${formatPercent(calledPct)} of commitment` : "—"
                }
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Distributed"
                value={formatCurrency(distributed, fund.currency_code, { compact: true })}
                caption="Lifetime"
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Remaining"
                value={formatCurrency(remaining, fund.currency_code, { compact: true })}
                caption="Uncalled commitment"
              />
            </CardSection>
          </div>
        </Card>

        {/* Pacing + inception side cards */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardSection>
              <Eyebrow>Pacing</Eyebrow>
              <p className="mt-3 font-sans text-[14px] leading-[1.55] text-ink-700">
                The fund has called {committed > 0 ? formatPercent(calledPct) : "—"} of committed
                capital{targetSize > 0 ? ` against a ${formatCurrency(targetSize, fund.currency_code, { compact: true })} target` : ""}.
              </p>
              <div className="mt-5 flex flex-col gap-2">
                <div className="flex justify-between font-sans text-[12px] text-ink-500">
                  <span>Called</span>
                  <span className="es-numeric">
                    {formatCurrency(called, fund.currency_code, { compact: true })} ·{" "}
                    {formatCurrency(committed, fund.currency_code, { compact: true })}
                  </span>
                </div>
                <ProgressBar value={calledPct} />
              </div>
              {targetSize > 0 && (
                <div className="mt-5 flex flex-col gap-2">
                  <div className="flex justify-between font-sans text-[12px] text-ink-500">
                    <span>Committed vs target</span>
                    <span className="es-numeric">{formatPercent(targetPct)}</span>
                  </div>
                  <ProgressBar value={targetPct} tone="brass" />
                </div>
              )}
            </CardSection>
          </Card>

          <Card raised>
            <CardSection>
              <Eyebrow>Inception</Eyebrow>
              <p className="mt-3 font-sans text-[14px] leading-[1.55] text-ink-700">
                {fund.inception_date
                  ? `Held since ${formatDateLong(fund.inception_date)}.`
                  : "Inception date not set."}{" "}
                Fund operates in {fund.currency_code}.
              </p>
              {fund.close_date && (
                <p className="mt-2 font-sans text-[13px] text-ink-500">
                  Closes {formatDateLong(fund.close_date)}.
                </p>
              )}
            </CardSection>
          </Card>
        </div>

        {/* Tabbed sections */}
        <div className="mt-12">
          <Tabs defaultValue="commitments" className="gap-6">
            <TabsList className="bg-parchment-100">
              <TabsTrigger value="commitments">
                Commitments
                <span className="ml-1 text-ink-500">({commitments.length})</span>
              </TabsTrigger>
              <TabsTrigger value="calls">
                Capital calls
                <span className="ml-1 text-ink-500">({calls.length})</span>
              </TabsTrigger>
              <TabsTrigger value="distributions">
                Distributions
                <span className="ml-1 text-ink-500">({distributions.length})</span>
              </TabsTrigger>
              <TabsTrigger value="team">
                Team
                <span className="ml-1 text-ink-500">({team.length})</span>
              </TabsTrigger>
              <TabsTrigger value="letters">
                Letters
                <span className="ml-1 text-ink-500">({letters.length})</span>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="commitments">
              <Card>
                <CardSection className="pt-2 pb-0">
                  {commitmentsQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : commitments.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-8">
                      <Eyebrow>No commitments yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Investor commitments to this fund will appear here once subscriptions are recorded.
                      </p>
                    </div>
                  ) : (
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
                        {commitments.map((c) => (
                          <TR key={c.id}>
                            <TD primary>{c.investor.name}</TD>
                            <TD align="right" primary>
                              {formatCurrency(parseDecimal(c.committed_amount), fund.currency_code, {
                                compact: true,
                              })}
                            </TD>
                            <TD align="right">
                              {formatCurrency(parseDecimal(c.called_amount), fund.currency_code, {
                                compact: true,
                              })}
                            </TD>
                            <TD align="right">
                              {formatCurrency(parseDecimal(c.distributed_amount), fund.currency_code, {
                                compact: true,
                              })}
                            </TD>
                            <TD align="right">
                              <StatusPill kind="commitment" value={c.status} />
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="calls">
              <Card>
                <CardSection className="pt-4">
                  {callsQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : calls.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-4">
                      <Eyebrow>No capital calls yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        When you issue a capital call against this fund, it will appear here.
                      </p>
                    </div>
                  ) : (
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {calls.map((c) => (
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
                              <span className="es-numeric">
                                {formatCurrency(parseDecimal(c.amount), fund.currency_code, {
                                  compact: true,
                                })}
                              </span>
                            </div>
                          </div>
                          <StatusPill kind="capital_call" value={c.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="distributions">
              <Card>
                <CardSection className="pt-4">
                  {distributionsQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : distributions.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-4">
                      <Eyebrow>No distributions yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Distributions issued to limited partners will appear here.
                      </p>
                    </div>
                  ) : (
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {distributions.map((d) => (
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
                              <span className="es-numeric">
                                {formatCurrency(parseDecimal(d.amount), fund.currency_code, {
                                  compact: true,
                                })}
                              </span>
                            </div>
                          </div>
                          <StatusPill kind="distribution" value={d.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="team">
              <Card>
                <CardSection>
                  {teamQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : team.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-2">
                      <Eyebrow>No team members assigned</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Assign analysts and partners to this fund to coordinate work.
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {team.map((member) => (
                        <span
                          key={member.id}
                          className="inline-flex items-center gap-2 border border-[color:var(--border-hairline)] bg-parchment-100 px-3 py-1.5 font-sans text-[13px] text-ink-900"
                        >
                          <span className="font-medium">User #{member.user_id}</span>
                          {member.title && (
                            <span className="text-ink-500">· {member.title}</span>
                          )}
                        </span>
                      ))}
                    </div>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="letters">
              <Card>
                <CardSection className="pt-4">
                  {lettersQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : letters.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-4">
                      <Eyebrow>No letters yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Quarterly letters and other communications sent against this fund will be listed here.
                      </p>
                      <Link
                        to="/letters"
                        className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700"
                      >
                        Drafting space →
                      </Link>
                    </div>
                  ) : (
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {letters.map((letter) => (
                        <li
                          key={letter.id}
                          className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"
                        >
                          <div className="flex flex-1 flex-col gap-1">
                            <span className="font-sans text-[14px] font-medium text-ink-900">
                              {letter.subject}
                            </span>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                              <span>{titleCase(letter.type)}</span>
                              {letter.sent_at && (
                                <>
                                  <span className="size-1 rounded-full bg-ink-300" />
                                  <span>Sent {formatDate(letter.sent_at)}</span>
                                </>
                              )}
                              {letter.recipients.length > 0 && (
                                <>
                                  <span className="size-1 rounded-full bg-ink-300" />
                                  <span>{letter.recipients.length} recipients</span>
                                </>
                              )}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardSection>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <FundEditDialog fund={fund} open={editOpen} onOpenChange={setEditOpen} />
    </>
  )
}

export default function FundDetailPage() {
  const { fundId: rawFundId } = useParams<{ fundId: string }>()
  const fundId = Number(rawFundId)

  if (!rawFundId || !Number.isFinite(fundId) || fundId <= 0) {
    return (
      <PageHero
        eyebrow="Programmes"
        title="Fund not found."
        description="The fund identifier in this URL is not valid."
      />
    )
  }

  return <FundDetailPageContent fundId={fundId} />
}
