import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import type { components } from "@/lib/schema"

type DocumentType = components["schemas"]["DocumentType"]

const DOCUMENT_TYPES: Array<{ value: DocumentType; label: string }> = [
  { value: "report", label: "Report" },
  { value: "financial", label: "Financial" },
  { value: "notice", label: "Notice" },
  { value: "legal", label: "Legal" },
  { value: "kyc_aml", label: "KYC / AML" },
  { value: "other", label: "Other" },
]

interface DocumentUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultFundId?: number
  defaultInvestorId?: number
  onCreated?: (documentId: number) => void
}

export function DocumentUploadDialog({
  open,
  onOpenChange,
  defaultFundId,
  defaultInvestorId,
  onCreated,
}: DocumentUploadDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState("")
  const [documentType, setDocumentType] = useState<DocumentType>("report")
  const [fundId, setFundId] = useState<string>(
    defaultFundId ? String(defaultFundId) : "none",
  )
  const [investorId, setInvestorId] = useState<string>(
    defaultInvestorId ? String(defaultInvestorId) : "none",
  )
  const [isConfidential, setIsConfidential] = useState(true)
  const [isUploading, setIsUploading] = useState(false)

  const queryClient = useQueryClient()
  const fundsQuery = useApiQuery("/funds", undefined, { enabled: open })
  const investorsQuery = useApiQuery("/investors", undefined, { enabled: open })

  const initUpload = useApiMutation("post", "/documents/upload-init")
  const createDocument = useApiMutation("post", "/documents")

  const submitting =
    isUploading || initUpload.isPending || createDocument.isPending

  function reset() {
    setFile(null)
    setTitle("")
    setDocumentType("report")
    setFundId(defaultFundId ? String(defaultFundId) : "none")
    setInvestorId(defaultInvestorId ? String(defaultInvestorId) : "none")
    setIsConfidential(true)
    setIsUploading(false)
  }

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null
    setFile(next)
    if (next && !title.trim()) {
      const stem = next.name.replace(/\.[^.]+$/, "")
      setTitle(stem)
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting || !file) return
    const trimmedTitle = title.trim()
    if (!trimmedTitle) return

    try {
      const init = await initUpload.mutateAsync({
        body: {
          file_name: file.name,
          mime_type: file.type || null,
          file_size: file.size,
        },
      })

      setIsUploading(true)
      const headers: Record<string, string> = {
        "Content-Type": file.type || "application/octet-stream",
      }
      if (init.upload_url.includes("/dev-storage/")) {
        headers["x-dev-storage-token"] = config.VITE_DEV_STORAGE_TOKEN
      }
      const uploadResponse = await fetch(init.upload_url, {
        method: "PUT",
        headers,
        body: file,
      })
      setIsUploading(false)
      if (!uploadResponse.ok) {
        toast.error("Upload failed", {
          description: `Storage responded with ${uploadResponse.status}`,
        })
        return
      }

      const created = await createDocument.mutateAsync({
        body: {
          title: trimmedTitle,
          document_type: documentType,
          file_name: file.name,
          file_url: init.file_url,
          mime_type: file.type || null,
          file_size: file.size,
          is_confidential: isConfidential,
          fund_id: fundId !== "none" ? Number(fundId) : null,
          investor_id: investorId !== "none" ? Number(investorId) : null,
        },
      })

      queryClient.invalidateQueries({ queryKey: ["/documents"] })

      toast.success("Document uploaded", { description: created.title })
      onCreated?.(created.id)
      reset()
      onOpenChange(false)
    } catch {
      setIsUploading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Upload document
          </DialogTitle>
          <DialogDescription>
            Files are stored privately. Confidential documents are visible only to
            limited partners with a commitment in the linked programme.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="document-file">File</Label>
            <Input
              id="document-file"
              type="file"
              onChange={handleFileChange}
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="document-title">Title</Label>
            <Input
              id="document-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Q2 2026 LP report"
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="document-type">Type</Label>
              <Select
                value={documentType}
                onValueChange={(value) =>
                  setDocumentType(value as DocumentType)
                }
              >
                <SelectTrigger id="document-type" className="w-full">
                  <SelectValue placeholder="Select a type" />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_TYPES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="document-fund">Fund (optional)</Label>
              <Select value={fundId} onValueChange={setFundId}>
                <SelectTrigger id="document-fund" className="w-full">
                  <SelectValue placeholder="Firm-wide" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Firm-wide</SelectItem>
                  {(fundsQuery.data ?? []).map((fund) => (
                    <SelectItem key={fund.id} value={String(fund.id)}>
                      {fund.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="document-investor">Investor (optional)</Label>
            <Select value={investorId} onValueChange={setInvestorId}>
              <SelectTrigger id="document-investor" className="w-full">
                <SelectValue placeholder="No specific investor" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No specific investor</SelectItem>
                {(investorsQuery.data ?? []).map((investor) => (
                  <SelectItem key={investor.id} value={String(investor.id)}>
                    {investor.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <input
              id="document-confidential"
              type="checkbox"
              checked={isConfidential}
              onChange={(event) => setIsConfidential(event.target.checked)}
              className="size-4 accent-conifer-700"
            />
            <Label htmlFor="document-confidential" className="font-sans text-sm">
              Confidential — log access on the audit ledger
            </Label>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={submitting || !file || !title.trim()}
            >
              {submitting && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Upload document
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
