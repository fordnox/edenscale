import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@edenscale/ui/button"
import { Checkbox } from "@edenscale/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@edenscale/ui/dialog"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import type { components } from "@edenscale/api/schema"

type DocumentType = components["schemas"]["DocumentType"]

const TYPE_OPTIONS: Array<{ value: DocumentType; label: string }> = [
  { value: "report", label: "Report" },
  { value: "financial", label: "Financial" },
  { value: "notice", label: "Notice" },
  { value: "legal", label: "Legal" },
  { value: "kyc_aml", label: "KYC / AML" },
  { value: "other", label: "Other" },
]

interface DocumentEditDialogProps {
  document: {
    id: string
    title: string
    document_type: DocumentType
    is_confidential: boolean
  }
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved?: () => void
}

/**
 * Edit a document's metadata (title, type, confidentiality). Shared by the
 * documents table row menu and the document detail drawer so both surfaces
 * offer the same edit affordance.
 */
export function DocumentEditDialog({
  document,
  open,
  onOpenChange,
  onSaved,
}: DocumentEditDialogProps) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(document.title)
  const [type, setType] = useState<DocumentType>(document.document_type)
  const [confidential, setConfidential] = useState(document.is_confidential)

  // Reseed from the document whenever the dialog opens.
  useEffect(() => {
    if (open) {
      setTitle(document.title)
      setType(document.document_type)
      setConfidential(document.is_confidential)
    }
  }, [open, document.title, document.document_type, document.is_confidential])

  const updateDocument = useApiMutation("patch", "/documents/{document_id}", {
    onSuccess: () => {
      toast.success("Document updated")
      queryClient.invalidateQueries({ queryKey: ["/documents"] })
      queryClient.invalidateQueries({
        queryKey: ["/documents/{document_id}"],
      })
      onOpenChange(false)
      onSaved?.()
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit document</DialogTitle>
          <DialogDescription>
            Update the title, classification, or confidentiality of this
            document.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="document-title">Title</Label>
            <Input
              id="document-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Type</Label>
            <Select
              value={type}
              onValueChange={(value) => setType(value as DocumentType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-2 font-sans text-[13px] text-ink-700">
            <Checkbox
              checked={confidential}
              onCheckedChange={(checked) => setConfidential(checked === true)}
            />
            Confidential (hidden from limited partners on fund-wide shares)
          </label>
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={updateDocument.isPending || title.trim() === ""}
            onClick={() =>
              updateDocument.mutate({
                params: { path: { document_id: document.id } },
                body: {
                  title: title.trim(),
                  document_type: type,
                  is_confidential: confidential,
                },
              })
            }
          >
            {updateDocument.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
