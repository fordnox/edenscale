import { Download, FileText, Loader2, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Eyebrow } from "@/components/ui/eyebrow"
import { useApiQuery } from "@/hooks/useApiQuery"
import { formatDate, titleCase } from "@/lib/format"

function formatBytes(n: number | null | undefined) {
  if (!n || n <= 0) return "—"
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

interface DocumentDetailProps {
  documentId: number
}

export function DocumentDetail({ documentId }: DocumentDetailProps) {
  const documentQuery = useApiQuery("/documents/{document_id}", {
    params: { path: { document_id: documentId } },
  })

  if (documentQuery.isLoading || !documentQuery.data) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
      </div>
    )
  }

  const doc = documentQuery.data
  const downloadUrl = doc.download_url ?? doc.file_url

  return (
    <div className="flex h-full flex-col">
      <div className="sticky top-0 z-10 border-b border-[color:var(--border-hairline)] bg-surface px-6 py-3">
        <Eyebrow>{titleCase(doc.document_type)}</Eyebrow>
        <h2 className="es-display mt-2 text-[22px] leading-tight md:text-[28px]">
          {doc.title}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-3 font-sans text-[12px] text-ink-500">
          <span className="break-all">{doc.file_name}</span>
          {doc.is_confidential && (
            <span className="inline-flex items-center gap-1">
              <Lock strokeWidth={1.5} className="size-3" />
              Confidential
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-2 gap-4 border-b border-[color:var(--border-hairline)] px-6 py-5">
          <div className="flex flex-col gap-1">
            <Eyebrow>Size</Eyebrow>
            <span className="es-numeric font-display text-[18px] text-ink-900">
              {formatBytes(doc.file_size)}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <Eyebrow>Uploaded</Eyebrow>
            <span className="font-sans text-[14px] text-ink-900">
              {doc.created_at ? formatDate(doc.created_at) : "—"}
            </span>
          </div>
          {doc.mime_type && (
            <div className="flex flex-col gap-1">
              <Eyebrow>Mime type</Eyebrow>
              <span className="es-numeric font-sans text-[12px] text-ink-700">
                {doc.mime_type}
              </span>
            </div>
          )}
          {doc.fund_id !== null && (
            <div className="flex flex-col gap-1">
              <Eyebrow>Fund</Eyebrow>
              <span className="font-sans text-[14px] text-ink-900">
                #{doc.fund_id}
              </span>
            </div>
          )}
          {doc.investor_id !== null && (
            <div className="flex flex-col gap-1">
              <Eyebrow>Investor</Eyebrow>
              <span className="font-sans text-[14px] text-ink-900">
                #{doc.investor_id}
              </span>
            </div>
          )}
        </div>

        <div className="px-6 py-5">
          <p className="font-sans text-[12px] leading-[1.5] text-ink-500">
            Download links are short-lived. Re-open the drawer to mint a fresh URL.
          </p>
        </div>

        <div className="flex items-start gap-3 border-t border-[color:var(--border-hairline)] px-6 py-5">
          <span className="mt-1 inline-flex size-8 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] bg-parchment-100 text-ink-700">
            <FileText strokeWidth={1.5} className="size-4" />
          </span>
          <p className="font-sans text-[12px] leading-[1.5] text-ink-700">
            Limited partners see only documents tied to programmes they hold a
            commitment in. Access is logged automatically and audited by counsel.
          </p>
        </div>
      </div>

      <div className="sticky bottom-0 z-10 border-t border-[color:var(--border-hairline)] bg-surface px-6 py-3">
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            asChild
            variant="primary"
            size="sm"
            className="min-h-11 w-full md:min-h-9 md:w-auto"
          >
            <a href={downloadUrl} target="_blank" rel="noopener noreferrer">
              <Download strokeWidth={1.5} className="size-4" />
              Download
            </a>
          </Button>
        </div>
      </div>
    </div>
  )
}
