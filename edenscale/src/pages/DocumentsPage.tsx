import { useState } from "react"
import { FileText, Lock, Download } from "lucide-react"
import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { DataTable, TH, TR, TD } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Eyebrow } from "@/components/ui/eyebrow"
import { documents, type DocumentType } from "@/data/mock"
import { formatDate, titleCase } from "@/lib/format"

const filters: Array<{ id: "all" | DocumentType; label: string }> = [
  { id: "all", label: "All" },
  { id: "report", label: "Reports" },
  { id: "financial", label: "Financial" },
  { id: "notice", label: "Notices" },
  { id: "legal", label: "Legal" },
  { id: "kyc_aml", label: "KYC / AML" },
  { id: "other", label: "Other" },
]

function formatBytes(n: number) {
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPage() {
  const [filter, setFilter] =
    useState<(typeof filters)[number]["id"]>("all")
  const list = documents.filter(
    (d) => filter === "all" || d.document_type === filter,
  )

  return (
    <>
      <Topbar
        eyebrow="Document library"
        title="Reports, notices, and counsel papers."
        description="Confidential by default. Releases to limited partners are logged on the audit ledger."
        actions={
          <Button variant="primary" size="sm">Upload document</Button>
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
            {list.length} of {documents.length} files
          </span>
        </div>

        <Card>
          <CardSection className="pt-2 pb-0">
            <DataTable>
              <thead>
                <tr>
                  <TH>Document</TH>
                  <TH>Linked to</TH>
                  <TH>Type</TH>
                  <TH align="right">Size</TH>
                  <TH align="right">Uploaded</TH>
                  <TH align="right" />
                </tr>
              </thead>
              <tbody>
                {list.map((d) => (
                  <TR key={d.id}>
                    <TD primary>
                      <div className="flex items-start gap-3">
                        <span className="mt-1 inline-flex size-8 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] bg-parchment-100 text-ink-700">
                          <FileText strokeWidth={1.5} className="size-4" />
                        </span>
                        <div className="flex flex-col gap-1">
                          <span>{d.title}</span>
                          <div className="flex items-center gap-2 font-sans text-[11px] font-normal text-ink-500">
                            <span>{d.file_name}</span>
                            {d.is_confidential && (
                              <>
                                <span className="size-1 rounded-full bg-ink-300" />
                                <span className="inline-flex items-center gap-1">
                                  <Lock
                                    strokeWidth={1.5}
                                    className="size-3"
                                  />
                                  Confidential
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </TD>
                    <TD>
                      {d.fund_name ?? d.investor_name ?? (
                        <span className="text-ink-500">Firm</span>
                      )}
                    </TD>
                    <TD>{titleCase(d.document_type)}</TD>
                    <TD align="right">{formatBytes(d.file_size)}</TD>
                    <TD align="right">
                      <div className="flex flex-col items-end leading-tight">
                        <span className="text-ink-900 text-[14px]">
                          {formatDate(d.created_at)}
                        </span>
                        <span className="text-[11px] text-ink-500">
                          by {d.uploaded_by}
                        </span>
                      </div>
                    </TD>
                    <TD align="right">
                      <Button variant="ghost" size="sm" aria-label="Download">
                        <Download
                          strokeWidth={1.5}
                          className="size-4 text-ink-500"
                        />
                      </Button>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          </CardSection>
        </Card>

        <div className="mt-12">
          <Eyebrow>A note on access</Eyebrow>
          <p className="mt-3 max-w-2xl font-sans text-[14px] leading-[1.55] text-ink-700">
            Limited partners see only documents tied to programmes they hold a
            commitment in. Access is logged automatically and audited quarterly
            by counsel.
          </p>
        </div>
      </div>
    </>
  )
}
