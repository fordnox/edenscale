import { Link, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useFundContext } from "@/layouts/FundLayout"
import { orgPath } from "@/lib/managerRoutes"
import { formatDate, titleCase } from "@edenscale/shared/format"

export default function FundDocumentsPage() {
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { fund } = useFundContext()

  const documentsQuery = useApiQuery("/documents", {
    params: { query: { fund_id: fund.id, limit: 5 } },
  })
  const documents = documentsQuery.data ?? []

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <Eyebrow>Documents ({documents.length})</Eyebrow>
      </div>
      <Card>
        <CardSection className="pt-4">
          {documentsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-4">
              <Eyebrow>No documents yet</Eyebrow>
              <p className="font-sans text-[14px] text-ink-700">
                Reports, notices, and counsel papers uploaded against this fund will be listed here.
              </p>
              <Link
                to={orgPath(orgSlug ?? "", "documents")}
                className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700"
              >
                Document library →
              </Link>
            </div>
          ) : (
            <ul className="divide-y divide-[color:var(--border-hairline)]">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"
                >
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="font-sans text-[14px] font-medium text-ink-900">
                      {doc.title}
                    </span>
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                      <span>{titleCase(doc.document_type)}</span>
                      {doc.created_at && (
                        <>
                          <span className="size-1 rounded-full bg-ink-300" />
                          <span>Uploaded {formatDate(doc.created_at)}</span>
                        </>
                      )}
                      {doc.file_size && (
                        <>
                          <span className="size-1 rounded-full bg-ink-300" />
                          <span>
                            {doc.file_size < 1024 * 1024
                              ? `${(doc.file_size / 1024).toFixed(0)} KB`
                              : `${(doc.file_size / (1024 * 1024)).toFixed(1)} MB`}
                          </span>
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
    </>
  )
}