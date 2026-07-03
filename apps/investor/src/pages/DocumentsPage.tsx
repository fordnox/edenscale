import { useMemo } from "react"
import { Helmet } from "react-helmet-async"
import { Download, Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatDate, titleCase } from "@edenscale/shared/format"

function formatBytes(size: number | null | undefined) {
  if (!size) return ""
  const units = ["B", "KB", "MB", "GB"]
  let value = size
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

export default function DocumentsPage() {
  const documentsQuery = useApiQuery("/documents")
  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  )

  return (
    <>
      <Helmet>
        <title>{`Documents · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Data room"
        title="Your documents."
        description="Reports, notices, and statements shared with you. Download links are private and time-limited."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          <CardSection className="pt-2 pb-0">
            {documentsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : documents.length === 0 ? (
              <EmptyState
                title="No documents"
                body="No documents have been shared with you yet."
              />
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Document</TH>
                    <TH>Fund</TH>
                    <TH align="right">Type</TH>
                    <TH align="right">Uploaded</TH>
                    <TH align="right">Download</TH>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <TR key={doc.id}>
                      <TD primary>
                        <div className="flex flex-col gap-1">
                          <span>{doc.title}</span>
                          <span className="font-sans text-[11px] font-normal text-ink-500">
                            {doc.file_name}
                            {doc.file_size ? ` · ${formatBytes(doc.file_size)}` : ""}
                          </span>
                        </div>
                      </TD>
                      <TD>{doc.fund_name ?? "—"}</TD>
                      <TD align="right">{titleCase(doc.document_type)}</TD>
                      <TD align="right">
                        {doc.created_at ? formatDate(doc.created_at) : "—"}
                      </TD>
                      <TD align="right">
                        {doc.download_url ? (
                          <Button asChild variant="ghost" size="sm" aria-label="Download">
                            <a
                              href={doc.download_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <Download strokeWidth={1.5} className="size-4" />
                            </a>
                          </Button>
                        ) : (
                          <span className="text-ink-500">—</span>
                        )}
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
