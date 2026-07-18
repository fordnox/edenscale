import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@edenscale/ui/button"
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
import { Textarea } from "@edenscale/ui/textarea"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import type { components } from "@edenscale/api/schema"

type CommunicationType = components["schemas"]["CommunicationType"]
type CommunicationRead = components["schemas"]["CommunicationRead"]

const TYPE_OPTIONS: Array<{ value: CommunicationType; label: string }> = [
  { value: "announcement", label: "Announcement" },
  { value: "message", label: "Message" },
  { value: "notification", label: "Notification" },
]

interface LetterComposeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultFundId?: string
  onCreated?: (letterId: string) => void
  /** When set, the dialog edits this existing draft (PATCH) instead of creating. */
  editLetter?: CommunicationRead | null
}

export function LetterComposeDialog({
  open,
  onOpenChange,
  defaultFundId,
  onCreated,
  editLetter,
}: LetterComposeDialogProps) {
  const isEditing = editLetter != null
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [type, setType] = useState<CommunicationType>("announcement")
  const [fundId, setFundId] = useState<string>(
    defaultFundId ? String(defaultFundId) : "none",
  )

  // Seed fields when the dialog opens: from the edited draft, or blank/default.
  useEffect(() => {
    if (!open) return
    if (editLetter) {
      setSubject(editLetter.subject)
      setBody(editLetter.body)
      setType(editLetter.type)
      setFundId(editLetter.fund_id ? String(editLetter.fund_id) : "none")
    } else {
      setSubject("")
      setBody("")
      setType("announcement")
      setFundId(defaultFundId ? String(defaultFundId) : "none")
    }
  }, [open, editLetter, defaultFundId])

  const queryClient = useQueryClient()
  const fundsQuery = useApiQuery("/funds", undefined, { enabled: open })

  const createLetter = useApiMutation("post", "/communications")
  const updateLetter = useApiMutation(
    "patch",
    "/communications/{communication_id}",
  )
  const sendLetter = useApiMutation(
    "post",
    "/communications/{communication_id}/send",
  )

  const submitting =
    createLetter.isPending || updateLetter.isPending || sendLetter.isPending

  function reset() {
    setSubject("")
    setBody("")
    setType("announcement")
    setFundId(defaultFundId ? String(defaultFundId) : "none")
  }

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    if (!next) reset()
    onOpenChange(next)
  }

  function invalidate(letterId?: string) {
    queryClient.invalidateQueries({ queryKey: ["/communications"] })
    if (letterId !== undefined) {
      queryClient.invalidateQueries({
        queryKey: [
          "/communications/{communication_id}",
          { params: { path: { communication_id: letterId } } },
        ],
      })
    }
    if (fundId !== "none") {
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/communications",
          { params: { path: { fund_id: fundId } } },
        ],
      })
    }
    queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
  }

  async function persistDraft(): Promise<string | null> {
    const trimmedSubject = subject.trim()
    const trimmedBody = body.trim()
    if (!trimmedSubject || !trimmedBody) return null
    const nextBody = {
      subject: trimmedSubject,
      body: trimmedBody,
      type,
      fund_id: fundId !== "none" ? fundId : null,
    }
    if (editLetter) {
      await updateLetter.mutateAsync({
        params: { path: { communication_id: editLetter.id } },
        body: nextBody,
      })
      return editLetter.id
    }
    const created = await createLetter.mutateAsync({ body: nextBody })
    return created.id
  }

  async function handleSaveDraft(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    try {
      const id = await persistDraft()
      if (id === null) return
      invalidate(id)
      toast.success(isEditing ? "Draft updated" : "Draft saved")
      onCreated?.(id)
      reset()
      onOpenChange(false)
    } catch {
      // useApiMutation surfaces a toast already
    }
  }

  async function handleSend() {
    if (submitting) return
    try {
      const id = await persistDraft()
      if (id === null) return
      await sendLetter.mutateAsync({
        params: { path: { communication_id: id } },
        body: null,
      })
      invalidate(id)
      toast.success("Letter sent")
      onCreated?.(id)
      reset()
      onOpenChange(false)
    } catch {
      // toast already surfaced
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            {isEditing ? "Edit draft" : "Draft a letter"}
          </DialogTitle>
          <DialogDescription>
            Send a quarterly letter or quick bulletin to limited partners. Saving
            as a draft does not deliver the note; sending records a delivery
            timestamp for every recipient.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={handleSaveDraft}
          className="flex flex-col gap-4"
          id="letter-compose-form"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="letter-type">Type</Label>
              <Select
                value={type}
                onValueChange={(value) => setType(value as CommunicationType)}
              >
                <SelectTrigger id="letter-type" className="w-full">
                  <SelectValue placeholder="Select a type" />
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
            <div className="flex flex-col gap-2">
              <Label htmlFor="letter-fund">Fund (optional)</Label>
              <Select value={fundId} onValueChange={setFundId}>
                <SelectTrigger id="letter-fund" className="w-full">
                  <SelectValue placeholder="Organization-wide" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Organization-wide</SelectItem>
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
            <Label htmlFor="letter-subject">Subject</Label>
            <Input
              id="letter-subject"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Q2 2026 — patience as a strategy"
              autoFocus
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="letter-body">Body</Label>
            <Textarea
              id="letter-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={10}
              placeholder="Write the letter in plain text. Rich formatting will arrive in a later release."
              required
            />
          </div>
          <DialogFooter className="pb-[env(safe-area-inset-bottom)]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="secondary"
              size="sm"
              className="min-h-11 md:min-h-9"
              disabled={submitting || !subject.trim() || !body.trim()}
            >
              {(createLetter.isPending || updateLetter.isPending) &&
                !sendLetter.isPending && (
                  <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                )}
              {isEditing ? "Save changes" : "Save draft"}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              onClick={handleSend}
              disabled={submitting || !subject.trim() || !body.trim()}
            >
              {sendLetter.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Send now
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
