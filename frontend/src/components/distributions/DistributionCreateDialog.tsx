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
import { Textarea } from "@/components/ui/textarea"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"

interface DistributionCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultFundId?: number
  onCreated?: (distributionId: number) => void
}

export function DistributionCreateDialog({
  open,
  onOpenChange,
  defaultFundId,
  onCreated,
}: DistributionCreateDialogProps) {
  const [fundId, setFundId] = useState<string>(
    defaultFundId ? String(defaultFundId) : "",
  )
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [distributionDate, setDistributionDate] = useState("")
  const [recordDate, setRecordDate] = useState("")
  const [amount, setAmount] = useState("")
  const [autoAllocate, setAutoAllocate] = useState(true)

  const queryClient = useQueryClient()
  const fundsQuery = useApiQuery("/funds", undefined, { enabled: open })

  const createDistribution = useApiMutation("post", "/distributions")
  const allocateProRata = useApiMutation(
    "post",
    "/distributions/{distribution_id}/items",
  )

  const submitting = createDistribution.isPending || allocateProRata.isPending

  function reset() {
    setFundId(defaultFundId ? String(defaultFundId) : "")
    setTitle("")
    setDescription("")
    setDistributionDate("")
    setRecordDate("")
    setAmount("")
    setAutoAllocate(true)
  }

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    if (!next) reset()
    onOpenChange(next)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const trimmedTitle = title.trim()
    const trimmedAmount = amount.trim()
    const numericFundId = Number(fundId)
    if (!trimmedTitle || !trimmedAmount || !distributionDate || !numericFundId)
      return

    try {
      const created = await createDistribution.mutateAsync({
        body: {
          fund_id: numericFundId,
          title: trimmedTitle,
          description: description.trim() || null,
          distribution_date: distributionDate,
          record_date: recordDate.trim() || null,
          amount: trimmedAmount,
        },
      })

      if (autoAllocate) {
        try {
          await allocateProRata.mutateAsync({
            params: {
              path: { distribution_id: created.id },
              query: { mode: "pro-rata" },
            },
            body: { items: [] },
          })
        } catch (allocationError) {
          const message =
            allocationError instanceof Error
              ? allocationError.message
              : "Pro-rata allocation failed"
          toast.warning("Distribution created without items", {
            description: message,
          })
        }
      }

      queryClient.invalidateQueries({ queryKey: ["/distributions"] })
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/distributions",
          { params: { path: { fund_id: numericFundId } } },
        ],
      })
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}",
          { params: { path: { fund_id: numericFundId } } },
        ],
      })
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/overview",
          { params: { path: { fund_id: numericFundId } } },
        ],
      })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })

      toast.success("Distribution created", { description: created.title })
      reset()
      onCreated?.(created.id)
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
            New distribution
          </DialogTitle>
          <DialogDescription>
            Schedule a return to limited partners. Pro-rata allocates the
            amount across all approved commitments by their committed share.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="distribution-fund">Fund</Label>
            <Select value={fundId} onValueChange={setFundId}>
              <SelectTrigger id="distribution-fund" className="w-full">
                <SelectValue placeholder="Select a fund" />
              </SelectTrigger>
              <SelectContent>
                {(fundsQuery.data ?? []).map((fund) => (
                  <SelectItem key={fund.id} value={String(fund.id)}>
                    {fund.name}
                    {fund.vintage_year ? ` · ${fund.vintage_year}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="distribution-title">Title</Label>
            <Input
              id="distribution-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Distribution #2 — Q2 2026"
              autoFocus
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="distribution-amount">Amount</Label>
              <Input
                id="distribution-amount"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="2500000"
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="distribution-date">Distribution date</Label>
              <Input
                id="distribution-date"
                type="date"
                value={distributionDate}
                onChange={(event) => setDistributionDate(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="distribution-record-date">
              Record date (optional)
            </Label>
            <Input
              id="distribution-record-date"
              type="date"
              value={recordDate}
              onChange={(event) => setRecordDate(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="distribution-description">Description</Label>
            <Textarea
              id="distribution-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="Source of proceeds, wire instructions, partner notes"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="distribution-auto-allocate"
              type="checkbox"
              checked={autoAllocate}
              onChange={(event) => setAutoAllocate(event.target.checked)}
              className="size-4 accent-conifer-700"
            />
            <Label
              htmlFor="distribution-auto-allocate"
              className="font-sans text-sm"
            >
              Auto-allocate pro-rata across approved commitments
            </Label>
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
                !title.trim() ||
                !amount.trim() ||
                !distributionDate ||
                !fundId
              }
            >
              {submitting && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Create distribution
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
