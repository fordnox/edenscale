import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useParams } from "react-router-dom"
import { toast } from "sonner"
import { Check, Copy, Download, FileText, Loader2, Lock, Mail } from "lucide-react"

import { DocumentDetail } from "@/components/documents/DocumentDetail"
import { DocumentUploadDialog } from "@/components/documents/DocumentUploadDialog"
import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatDate, titleCase } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type DocumentType = components["schemas"]["DocumentType"]

const TYPE_FILTERS: Array<{ id: "all" | DocumentType; label: string }> = [
  { id: "all", label: "All" },
  { id: "report", label: "Reports" },
  { id: "financial", label: "Financial" },
  { id: "notice", label: "Notices" },
  { id: "legal", label: "Legal" },
  { id: "kyc_aml", label: "KYC / AML" },
  { id: "other", label: "Other" },
]

function formatBytes(n: number | null | undefined) {
  if (!n || n <= 0) return "—"
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export default function DocumentsPage() {
  const { activeMembership } = useActiveOrganization()
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const canManage =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  // Attachments emailed to this address land in this org's library (see the
  // email-ingest Worker). The +<org-slug> tag selects the org, so the address
  // is org-specific.
  const ingestAddress = orgSlug ? `ingest+${orgSlug}@newtaven.com` : null
  const [addressCopied, setAddressCopied] = useState(false)

  const copyIngestAddress = async () => {
    if (!ingestAddress) return
    try {
      await navigator.clipboard.writeText(ingestAddress)
      setAddressCopied(true)
      toast.success("Email address copied")
      window.setTimeout(() => setAddressCopied(false), 2000)
    } catch {
      toast.error("Could not copy — copy the address manually")
    }
  }

  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<"all" | DocumentType>("all")
  const [fundFilter, setFundFilter] = useState<"all" | string>("all")
  const [investorFilter, setInvestorFilter] = useState<"all" | string>("all")

  const fundsQuery = useApiQuery("/funds")
  const investorsQuery = useApiQuery("/investors")

  const documentsQuery = useApiQuery("/documents", {
    params: {
      query: {
        ...(typeFilter !== "all" ? { document_type: typeFilter } : {}),
        ...(fundFilter !== "all" ? { fund_id: fundFilter } : {}),
        ...(investorFilter !== "all"
          ? { investor_id: investorFilter }
          : {}),
      },
    },
  })

  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  )

  const fundNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const f of fundsQuery.data ?? []) map.set(f.id, f.name)
    return map
  }, [fundsQuery.data])

  const investorNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const i of investorsQuery.data ?? []) map.set(i.id, i.name)
    return map
  }, [investorsQuery.data])

  return (
    <>
      <Helmet>
        <title>{`Documents · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Document library"
        title="Reports, notices, and counsel papers."
        description="Confidential by default. Releases to limited partners are logged on the audit ledger."
        actions={
          canManage ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setUploadOpen(true)}
            >
              Upload document
            </Button>
          ) : undefined
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setTypeFilter(f.id)}
              className={
                "rounded-xs border px-3.5 py-1.5 font-sans text-[12px] tracking-tight transition-colors " +
                (typeFilter === f.id
                  ? "border-conifer-700 bg-conifer-700 text-parchment-50"
                  : "border-[color:var(--border-hairline)] bg-surface text-ink-700 hover:border-[color:var(--border-default)]")
              }
            >
              {f.label}
            </button>
          ))}
          <span className="ml-auto font-sans text-[12px] text-ink-500">
            {documents.length} file{documents.length === 1 ? "" : "s"}
          </span>
        </div>

        {canManage && ingestAddress && (
          <div className="mb-4 flex flex-col gap-3 border border-[color:var(--border-hairline)] bg-parchment-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] bg-surface text-ink-700">
                <Mail strokeWidth={1.5} className="size-4" />
              </span>
              <div className="flex flex-col gap-1">
                <span className="font-sans text-[13px] font-medium text-ink-800">
                  Upload by email
                </span>
                <span className="font-sans text-[12px] leading-relaxed text-ink-500">
                  Forward or CC any message to{" "}
                  <code className="rounded-xs bg-surface px-1.5 py-0.5 font-mono text-[12px] text-ink-800">
                    {ingestAddress}
                  </code>{" "}
                  and its attachments are added to this organization's library
                  automatically.
                </span>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="shrink-0 gap-2"
              onClick={copyIngestAddress}
            >
              {addressCopied ? (
                <Check strokeWidth={1.5} className="size-4" />
              ) : (
                <Copy strokeWidth={1.5} className="size-4" />
              )}
              {addressCopied ? "Copied" : "Copy address"}
            </Button>
          </div>
        )}

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Eyebrow>Fund</Eyebrow>
            <Select value={fundFilter} onValueChange={setFundFilter}>
              <SelectTrigger className="min-w-[200px]">
                <SelectValue placeholder="All funds" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All funds</SelectItem>
                {(fundsQuery.data ?? []).map((fund) => (
                  <SelectItem key={fund.id} value={String(fund.id)}>
                    {fund.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Eyebrow>Investor</Eyebrow>
            <Select value={investorFilter} onValueChange={setInvestorFilter}>
              <SelectTrigger className="min-w-[200px]">
                <SelectValue placeholder="All investors" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All investors</SelectItem>
                {(investorsQuery.data ?? []).map((investor) => (
                  <SelectItem key={investor.id} value={String(investor.id)}>
                    {investor.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Card>
          <CardSection className="pt-2 pb-0">
            {documentsQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : documents.length === 0 ? (
              <EmptyState
                icon={<FileText strokeWidth={1.25} />}
                title="No documents match these filters"
                body={
                  canManage
                    ? "Try clearing the filters above, or upload a new document to begin the library."
                    : "Try clearing the filters above. Documents shared with you will appear here."
                }
                action={
                  canManage ? (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setUploadOpen(true)}
                    >
                      Upload document
                    </Button>
                  ) : undefined
                }
              />
            ) : (
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
                  {documents.map((doc) => {
                    const fundName =
                      doc.fund_name ??
                      (doc.fund_id !== null
                        ? (fundNameById.get(doc.fund_id) ?? null)
                        : null)
                    const investorName =
                      doc.investor_name ??
                      (doc.investor_id !== null
                        ? (investorNameById.get(doc.investor_id) ?? null)
                        : null)
                    const linkedTo = fundName ?? investorName ?? null
                    const downloadUrl = doc.download_url ?? doc.file_url
                    return (
                      <TR
                        key={doc.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(doc.id)}
                      >
                        <TD primary>
                          <div className="flex items-start gap-3">
                            <span className="mt-1 inline-flex size-8 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] bg-parchment-100 text-ink-700">
                              <FileText strokeWidth={1.5} className="size-4" />
                            </span>
                            <div className="flex flex-col gap-1">
                              <span>{doc.title}</span>
                              <div className="flex items-center gap-2 font-sans text-[11px] font-normal text-ink-500">
                                <span>{doc.file_name}</span>
                                {doc.is_confidential && (
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
                          {linkedTo ?? (
                            <span className="text-ink-500">Organization</span>
                          )}
                        </TD>
                        <TD>{titleCase(doc.document_type)}</TD>
                        <TD align="right">{formatBytes(doc.file_size)}</TD>
                        <TD align="right">
                          {doc.created_at ? formatDate(doc.created_at) : "—"}
                        </TD>
                        <TD align="right">
                          <Button
                            asChild
                            variant="ghost"
                            size="sm"
                            aria-label="Download"
                            onClick={(event) => event.stopPropagation()}
                          >
                            <a
                              href={downloadUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <Download
                                strokeWidth={1.5}
                                className="size-4 text-ink-500"
                              />
                            </a>
                          </Button>
                        </TD>
                      </TR>
                    )
                  })}
                </tbody>
              </DataTable>
            )}
          </CardSection>
        </Card>
      </div>

      <Sheet
        open={selectedId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Document detail</SheetTitle>
          <SheetDescription className="sr-only">
            Metadata and a fresh download link for the selected document.
          </SheetDescription>
          {selectedId !== null && (
            <DocumentDetail
              key={selectedId}
              documentId={selectedId}
              onDeleted={() => setSelectedId(null)}
            />
          )}
        </SheetContent>
      </Sheet>

      <DocumentUploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onCreated={(id) => setSelectedId(id)}
      />
    </>
  )
}
