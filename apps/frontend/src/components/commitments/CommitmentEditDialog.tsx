import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Check, Loader2, X } from "lucide-react"
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
import { StatusPill } from "@/components/ui/StatusPill"
import { Textarea } from "@/components/ui/textarea"
import { useApiMutation } from "@/hooks/useApiMutation"
import type { components } from "@/lib/schema"

type CommitmentRead = components["schemas"]["CommitmentRead"]
type CommitmentStatus = components["schemas"]["CommitmentStatus"]

const TERMINAL_STATUSES: readonly CommitmentStatus[] = ["declined", "cancelled"]

interface CommitmentEditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  commitment: CommitmentRead
  /** Fund the commitment belongs to — used to invalidate fund-scoped queries. */
  fundId: string
}

export function CommitmentEditDialog({
  open,
  onOpenChange,
  commitment,
  fundId,
}: CommitmentEditDialogProps) {
  const [committedAmount, setCommittedAmount] = useState(
    commitment.committed_amount,
  )
  const [commitmentDate, setCommitmentDate] = useState(
    commitment.commitment_date,
  )
  const [shareClass, setShareClass] = useState(commitment.share_class ?? "")
  const [notes, setNotes] = useState(commitment.notes ?? "")

  const queryClient = useQueryClient()

  useEffect(() => {
    if (open) {
      setCommittedAmount(commitment.committed_amount)
      setCommitmentDate(commitment.commitment_date)
      setShareClass(commitment.share_class ?? "")
      setNotes(commitment.notes ?? "")
    }
  }, [open, commitment])

  const updateCommitment = useApiMutation("patch", "/commitments/{commitment_id}")
  const updateStatus = useApiMutation(
    "post",
    "/commitments/{commitment_id}/status",
  )
  const submitting = updateCommitment.isPending || updateStatus.isPending

  const isTerminal = TERMINAL_STATUSES.includes(commitment.status)
  const isPending = commitment.status === "pending"

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    onOpenChange(next)
  }

  function invalidate() {
    queryClient.invalidateQueries({
      queryKey: [
        "/funds/{fund_id}/commitments",
        { params: { path: { fund_id: fundId } } },
      ],
    })
    queryClient.invalidateQueries({
      queryKey: ["/funds/{fund_id}", { params: { path: { fund_id: fundId } } }],
    })
    queryClient.invalidateQueries({
      queryKey: [
        "/funds/{fund_id}/overview",
        { params: { path: { fund_id: fundId } } },
      ],
    })
    queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const trimmedAmount = committedAmount.trim()
    if (!trimmedAmount || !commitmentDate) return

    try {
      await updateCommitment.mutateAsync({
        params: { path: { commitment_id: commitment.id } },
        body: {
          committed_amount: trimmedAmount,
          commitment_date: commitmentDate,
          share_class: shareClass.trim() || null,
          notes: notes.trim() || null,
        },
      })
      invalidate()
      toast.success("Commitment updated", {
        description: commitment.investor.name,
      })
      onOpenChange(false)
    } catch {
      // useApiMutation surfaces a toast already; nothing else to do here
    }
  }

  async function handleStatus(status: CommitmentStatus) {
    if (submitting) return
    try {
      await updateStatus.mutateAsync({
        params: { path: { commitment_id: commitment.id } },
        body: { status },
      })
      invalidate()
      toast.success(status === "approved" ? "Commitment approved" : "Commitment declined", {
        description: commitment.investor.name,
      })
      onOpenChange(false)
    } catch {
      // useApiMutation surfaces a toast already; nothing else to do here
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Edit commitment
          </DialogTitle>
          <DialogDescription>{commitment.investor.name}</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <span className="font-sans text-[12px] text-ink-500">Status</span>
          <StatusPill kind="commitment" value={commitment.status} />
        </div>

        {isPending && (
          <div className="flex flex-wrap items-center gap-2 border-y border-[color:var(--border-hairline)] py-3">
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => handleStatus("approved")}
              disabled={submitting || isTerminal}
            >
              {updateStatus.isPending ? (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              ) : (
                <Check strokeWidth={1.5} className="size-4" />
              )}
              Approve
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleStatus("declined")}
              disabled={submitting || isTerminal}
            >
              <X strokeWidth={1.5} className="size-4" />
              Decline
            </Button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="commitment-edit-amount">Committed amount</Label>
              <Input
                id="commitment-edit-amount"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                value={committedAmount}
                onChange={(event) => setCommittedAmount(event.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="commitment-edit-date">Commitment date</Label>
              <Input
                id="commitment-edit-date"
                type="date"
                value={commitmentDate}
                onChange={(event) => setCommitmentDate(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="commitment-edit-share-class">
              Share class (optional)
            </Label>
            <Input
              id="commitment-edit-share-class"
              value={shareClass}
              onChange={(event) => setShareClass(event.target.value)}
              placeholder="Class A"
              maxLength={100}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="commitment-edit-notes">Notes</Label>
            <Textarea
              id="commitment-edit-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
              placeholder="Side-letter terms, subscription reference, partner notes"
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
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={submitting || !committedAmount.trim() || !commitmentDate}
            >
              {updateCommitment.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
