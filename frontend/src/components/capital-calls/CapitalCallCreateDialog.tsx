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

interface CapitalCallCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultFundId?: number
  onCreated?: (callId: number) => void
}

export function CapitalCallCreateDialog({
  open,
  onOpenChange,
  defaultFundId,
  onCreated,
}: CapitalCallCreateDialogProps) {
  const [fundId, setFundId] = useState<string>(
    defaultFundId ? String(defaultFundId) : "",
  )
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [callDate, setCallDate] = useState("")
  const [amount, setAmount] = useState("")
  const [autoAllocate, setAutoAllocate] = useState(true)

  const queryClient = useQueryClient()
  const fundsQuery = useApiQuery("/funds", undefined, { enabled: open })

  const createCall = useApiMutation("post", "/capital-calls")
  const allocateProRata = useApiMutation(
    "post",
    "/capital-calls/{call_id}/items",
  )

  const submitting = createCall.isPending || allocateProRata.isPending

  function reset() {
    setFundId(defaultFundId ? String(defaultFundId) : "")
    setTitle("")
    setDescription("")
    setDueDate("")
    setCallDate("")
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
    if (!trimmedTitle || !trimmedAmount || !dueDate || !numericFundId) return

    try {
      const created = await createCall.mutateAsync({
        body: {
          fund_id: numericFundId,
          title: trimmedTitle,
          description: description.trim() || null,
          due_date: dueDate,
          call_date: callDate.trim() || null,
          amount: trimmedAmount,
        },
      })

      if (autoAllocate) {
        try {
          await allocateProRata.mutateAsync({
            params: {
              path: { call_id: created.id },
              query: { mode: "pro-rata" },
            },
            body: { items: [] },
          })
        } catch (allocationError) {
          const message =
            allocationError instanceof Error
              ? allocationError.message
              : "Pro-rata allocation failed"
          toast.warning("Capital call created without items", {
            description: message,
          })
        }
      }

      queryClient.invalidateQueries({ queryKey: ["/capital-calls"] })
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/capital-calls",
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

      toast.success("Capital call created", { description: created.title })
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
          <DialogTitle className="es-display text-[24px]">New capital call</DialogTitle>
          <DialogDescription>
            Issue a drawdown against a fund. Pro-rata allocates the amount across all
            approved commitments by their committed share.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="call-fund">Fund</Label>
            <Select value={fundId} onValueChange={setFundId}>
              <SelectTrigger id="call-fund" className="w-full">
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
            <Label htmlFor="call-title">Title</Label>
            <Input
              id="call-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Drawdown #4 — Q2 2026"
              autoFocus
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="call-amount">Amount</Label>
              <Input
                id="call-amount"
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
              <Label htmlFor="call-due">Due date</Label>
              <Input
                id="call-due"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="call-call-date">Call date (optional)</Label>
            <Input
              id="call-call-date"
              type="date"
              value={callDate}
              onChange={(event) => setCallDate(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="call-description">Description</Label>
            <Textarea
              id="call-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="Use of proceeds, wire instructions, partner notes"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              id="call-auto-allocate"
              type="checkbox"
              checked={autoAllocate}
              onChange={(event) => setAutoAllocate(event.target.checked)}
              className="size-4 accent-conifer-700"
            />
            <Label htmlFor="call-auto-allocate" className="font-sans text-sm">
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
                !dueDate ||
                !fundId
              }
            >
              {submitting && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Create capital call
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
