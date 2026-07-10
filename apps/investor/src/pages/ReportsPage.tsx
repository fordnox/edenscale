import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Download, FileBarChart, Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatDate } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type DocumentRead = components["schemas"]["DocumentRead"]

interface FundReports {
  fundId: string
  fundName: string
  reports: DocumentRead[]
}

export default function ReportsPage() {
  const documentsQuery = useApiQuery("/investor/documents")

  const grouped = useMemo<FundReports[]>(() => {
    const reports = (documentsQuery.data ?? []).filter(
      (d) => d.document_type === "report",
    )
    const byFund = new Map<string, FundReports>()
    for (const r of reports) {
      const key = r.fund_id ?? "__none__"
      const name = r.fund_name ?? "Firm-wide"
      const existing = byFund.get(key)
      if (existing) existing.reports.push(r)
      else byFund.set(key, { fundId: key, fundName: name, reports: [r] })
    }
    // Newest report first within each fund, and funds by their latest report.
    for (const group of byFund.values()) {
      group.reports.sort((a, b) =>
        (a.created_at ?? "") < (b.created_at ?? "") ? 1 : -1,
      )
    }
    return [...byFund.values()].sort((a, b) =>
      (a.reports[0]?.created_at ?? "") < (b.reports[0]?.created_at ?? "") ? 1 : -1,
    )
  }, [documentsQuery.data])

  return (
    <>
      <Helmet>
        <title>{`Investor reports · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Investor reports"
        title="Your reports."
        description="Quarterly and annual reports for the funds you hold. Open the latest, or browse the history per fund."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {documentsQuery.isLoading ? (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : grouped.length === 0 ? (
          <Card>
            <EmptyState
              icon={<FileBarChart strokeWidth={1.25} />}
              title="No reports yet"
              body="Investor reports shared with you will appear here."
            />
          </Card>
        ) : (
          <div className="flex flex-col gap-8">
            {grouped.map((group) => {
              const [latest, ...older] = group.reports
              return (
                <section key={group.fundId}>
                  <Eyebrow>{group.fundName}</Eyebrow>
                  <Card className="mt-4">
                    <CardSection>
                      {/* Latest report — highlighted */}
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 inline-flex size-10 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
                            <FileBarChart strokeWidth={1.5} className="size-5" />
                          </span>
                          <div className="flex flex-col gap-1">
                            <span className="font-display text-[20px] leading-tight text-ink-900">
                              {latest.title}
                            </span>
                            <span className="font-sans text-[12px] text-ink-500">
                              {latest.created_at
                                ? `Published ${formatDate(latest.created_at)}`
                                : "Latest report"}
                            </span>
                          </div>
                        </div>
                        {latest.download_url && (
                          <div className="flex shrink-0 gap-2">
                            <Button asChild variant="primary" size="sm">
                              <a
                                href={latest.download_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                View report
                              </a>
                            </Button>
                            <Button asChild variant="secondary" size="sm">
                              <a href={latest.download_url} download>
                                <Download strokeWidth={1.5} className="size-4" />
                                Download
                              </a>
                            </Button>
                          </div>
                        )}
                      </div>

                      {/* Older reports */}
                      {older.length > 0 && (
                        <ul className="mt-6 divide-y divide-[color:var(--border-hairline)] border-t border-[color:var(--border-hairline)]">
                          {older.map((r) => (
                            <li
                              key={r.id}
                              className="flex items-center justify-between gap-4 py-3"
                            >
                              <div className="flex flex-col">
                                <span className="font-sans text-[14px] text-ink-900">
                                  {r.title}
                                </span>
                                <span className="font-sans text-[11px] text-ink-500">
                                  {r.created_at ? formatDate(r.created_at) : "—"}
                                </span>
                              </div>
                              {r.download_url && (
                                <a
                                  href={r.download_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="shrink-0 font-sans text-[13px] text-conifer-700 underline-offset-4 hover:underline"
                                >
                                  View
                                </a>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </CardSection>
                  </Card>
                </section>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
