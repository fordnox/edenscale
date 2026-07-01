import { useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"

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
import { Textarea } from "@/components/ui/textarea"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { toast } from "sonner"
import { titleCase } from "@/lib/format"
import type { components } from "@/lib/schema"

type CommitmentStatus = components["schemas"]["CommitmentStatus"]

const STATUS_OPTIONS: readonly CommitmentStatus[] = [
  "pending",
  "approved",
] as const

/** Fund is fixed; the user picks which investor is subscribing. */
interface FundContext {
  kind: "fund"
  fundId: string
  fundName: string
  /** Investor ids already committed to this fund — excluded from the picker. */
  existingInvestorIds?: readonly string[]
}

/** Investor is fixed; the user picks which fund they are subscribing to. */
interface InvestorContext {
  kind: "investor"
  investorId: string
  investorName: string
  /** Fund ids this investor already has a commitment to — excluded. */
  existingFundIds?: readonly string[]
}

type CommitmentContext = FundContext | InvestorContext

interface CommitmentCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  context: CommitmentContext
  onCreated?: (commitmentId: string) => void
}

export function CommitmentCreateDialog({
  open,
  onOpenChange,
  context,
  onCreated,
}: CommitmentCreateDialogProps) {
  const isFundMode = context.kind === "fund"
  const pickNoun = isFundMode ? "investor" : "fund"

  const [selectedId, setSelectedId] = useState("")
  const [committedAmount, setCommittedAmount] = useState("")
  const [commitmentDate, setCommitmentDate] = useState("")
  const [status, setStatus] = useState<CommitmentStatus>("pending")
  const [shareClass, setShareClass] = useState("")
  const [notes, setNotes] = useState("")

  const queryClient = useQueryClient()
  // Only the picker relevant to the current mode is fetched.
  const investorsQuery = useApiQuery("/investors", undefined, {
    enabled: open && isFundMode,
  })
  const fundsQuery = useApiQuery("/funds", undefined, {
    enabled: open && !isFundMode,
  })

  const createCommitment = useApiMutation("post", "/commitments")
  const submitting = createCommitment.isPending

  const optionsLoading = isFundMode
    ? investorsQuery.isLoading
    : fundsQuery.isLoading

  const options = useMemo(() => {
    if (context.kind === "fund") {
      const taken = new Set(context.existingInvestorIds ?? [])
      return (investorsQuery.data ?? [])
        .filter((inv) => !taken.has(inv.id))
        .map((inv) => ({
          id: inv.id,
          label: inv.investor_code
            ? `${inv.name} · ${inv.investor_code}`
            : inv.name,
        }))
    }
    const taken = new Set(context.existingFundIds ?? [])
    return (fundsQuery.data ?? [])
      .filter((fund) => !taken.has(fund.id))
      .map((fund) => ({
        id: fund.id,
        label: fund.vintage_year ? `${fund.name} · ${fund.vintage_year}` : fund.name,
      }))
  }, [context, investorsQuery.data, fundsQuery.data])

  function reset() {
    setSelectedId("")
    setCommittedAmount("")
    setCommitmentDate("")
    setStatus("pending")
    setShareClass("")
    setNotes("")
  }

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    if (!next) reset()
    onOpenChange(next)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const trimmedAmount = committedAmount.trim()
    if (!selectedId || !trimmedAmount || !commitmentDate) return

    const fundId = context.kind === "fund" ? context.fundId : selectedId
    const investorId = context.kind === "fund" ? selectedId : context.investorId

    try {
      const created = await createCommitment.mutateAsync({
        body: {
          fund_id: fundId,
          investor_id: investorId,
          committed_amount: trimmedAmount,
          called_amount: "0",
          distributed_amount: "0",
          commitment_date: commitmentDate,
          status,
          share_class: shareClass.trim() || null,
          notes: notes.trim() || null,
        },
      })

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
      queryClient.invalidateQueries({
        queryKey: [
          "/investors/{investor_id}/commitments",
          { params: { path: { investor_id: investorId } } },
        ],
      })
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })

      toast.success("Commitment recorded", {
        description:
          context.kind === "fund" ? created.investor.name : created.fund.name,
      })
      reset()
      onCreated?.(created.id)
      onOpenChange(false)
    } catch {
      // useApiMutation surfaces a toast already; nothing else to do here
    }
  }

  const description =
    context.kind === "fund"
      ? `Record an investor's subscription to ${context.fundName}. Called and distributed amounts accrue from capital calls and distributions.`
      : `Record ${context.investorName}'s subscription to a fund. Called and distributed amounts accrue from capital calls and distributions.`

  const emptyNote =
    context.kind === "fund"
      ? "Every investor already has a commitment to this fund."
      : "This investor is already committed to every fund."

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">New commitment</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="commitment-pick">{titleCase(pickNoun)}</Label>
            <Select value={selectedId} onValueChange={setSelectedId}>
              <SelectTrigger id="commitment-pick" className="w-full">
                <SelectValue
                  placeholder={
                    optionsLoading
                      ? `Loading ${pickNoun}s…`
                      : options.length === 0
                        ? `No ${pickNoun}s available`
                        : `Select ${isFundMode ? "an" : "a"} ${pickNoun}`
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {options.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!optionsLoading && options.length === 0 && (
              <p className="font-sans text-[12px] text-ink-500">{emptyNote}</p>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="commitment-amount">Committed amount</Label>
              <Input
                id="commitment-amount"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                value={committedAmount}
                onChange={(event) => setCommittedAmount(event.target.value)}
                placeholder="5000000"
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="commitment-date">Commitment date</Label>
              <Input
                id="commitment-date"
                type="date"
                value={commitmentDate}
                onChange={(event) => setCommitmentDate(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="commitment-status">Status</Label>
              <Select
                value={status}
                onValueChange={(value) => setStatus(value as CommitmentStatus)}
              >
                <SelectTrigger id="commitment-status" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {titleCase(option)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="commitment-share-class">Share class (optional)</Label>
              <Input
                id="commitment-share-class"
                value={shareClass}
                onChange={(event) => setShareClass(event.target.value)}
                placeholder="Class A"
                maxLength={100}
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="commitment-notes">Notes</Label>
            <Textarea
              id="commitment-notes"
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
              disabled={
                submitting ||
                !selectedId ||
                !committedAmount.trim() ||
                !commitmentDate
              }
            >
              {submitting && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Record commitment
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
