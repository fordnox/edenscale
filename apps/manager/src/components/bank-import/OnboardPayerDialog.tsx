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
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import type { components } from "@edenscale/api/schema"

type InvestorRead = components["schemas"]["InvestorRead"]
type CommitmentStatus = components["schemas"]["CommitmentStatus"]
type MatchCandidate = components["schemas"]["MatchCandidate"]

type Step = "investor" | "commitment" | "callitem"

interface OnboardPayerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Payer name from the bank statement, used to prefill the investor name. */
  defaultName: string
  /** Debtor IBAN, if the statement carried one — stashed in investor notes. */
  iban?: string | null
  /** Payment amount, used to prefill the commitment and allocation amounts. */
  amount: string
  /** Payment currency, used to flag currency mismatch on the new candidate. */
  currency?: string | null
  /** Value date, used to prefill the commitment date. */
  valueDate?: string | null
  /**
   * Called when the flow closes. `candidate` is a ready-to-assign match for the
   * originating transaction when the payer was allocated onto a capital call,
   * otherwise null (investor/commitment created but not allocated).
   */
  onCompleted?: (candidate: MatchCandidate | null) => void
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function toNumber(value: string | null | undefined): number {
  if (!value) return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

/**
 * Onboard a bank-statement payer inline, all the way to an assignable payment:
 * create the investor, a commitment in a fund, then allocate that commitment
 * onto an existing capital call. The resulting capital-call item is handed back
 * as a MatchCandidate so the wizard can settle this payment against it without
 * re-parsing the statement. Every step is skippable; earlier steps persist.
 */
export function OnboardPayerDialog({
  open,
  onOpenChange,
  defaultName,
  iban,
  amount,
  currency,
  valueDate,
  onCompleted,
}: OnboardPayerDialogProps) {
  const [step, setStep] = useState<Step>("investor")

  // Step 1 — investor
  const [name, setName] = useState(defaultName)
  const [investorCode, setInvestorCode] = useState("")
  const [investor, setInvestor] = useState<InvestorRead | null>(null)

  // Step 2 — commitment
  const [fundId, setFundId] = useState("")
  const [committedAmount, setCommittedAmount] = useState(amount)
  const [commitmentDate, setCommitmentDate] = useState(valueDate ?? todayIso())
  const [status, setStatus] = useState<CommitmentStatus>("approved")
  const [commitmentId, setCommitmentId] = useState<string | null>(null)

  // Step 3 — capital-call allocation
  const [callId, setCallId] = useState("")
  const [allocationAmount, setAllocationAmount] = useState(amount)

  const queryClient = useQueryClient()
  const fundsQuery = useApiQuery("/funds", undefined, { enabled: open })
  const callsQuery = useApiQuery(
    "/capital-calls",
    { params: { query: { fund_id: fundId } } },
    { enabled: open && step === "callitem" && fundId !== "" },
  )
  const createInvestor = useApiMutation("post", "/investors")
  const createCommitment = useApiMutation("post", "/commitments")
  const createItems = useApiMutation("post", "/capital-calls/{call_id}/items")

  // Reset the whole flow each time the dialog opens for a new payer.
  useEffect(() => {
    if (open) {
      setStep("investor")
      setName(defaultName)
      setInvestorCode("")
      setInvestor(null)
      setFundId("")
      setCommittedAmount(amount)
      setCommitmentDate(valueDate ?? todayIso())
      setStatus("approved")
      setCommitmentId(null)
      setCallId("")
      setAllocationAmount(amount)
    }
  }, [open, defaultName, amount, valueDate])

  async function handleCreateInvestor(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed || createInvestor.isPending) return
    try {
      const created = await createInvestor.mutateAsync({
        body: {
          name: trimmed,
          accredited: false,
          ...(investorCode.trim()
            ? { investor_code: investorCode.trim() }
            : {}),
          ...(iban ? { notes: `IBAN: ${iban}` } : {}),
        },
      })
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      setInvestor(created)
      setStep("commitment")
      toast.success("Investor added", { description: created.name })
    } catch {
      // Non-401 errors surface through the api client's toast middleware.
    }
  }

  async function handleCreateCommitment(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()
    if (!investor || !fundId || createCommitment.isPending) return
    try {
      const created = await createCommitment.mutateAsync({
        body: {
          fund_id: fundId,
          investor_id: investor.id,
          committed_amount: toNumber(committedAmount).toFixed(2),
          called_amount: "0",
          distributed_amount: "0",
          commitment_date: commitmentDate,
          status,
        },
      })
      queryClient.invalidateQueries({ queryKey: ["/commitments"] })
      setCommitmentId(created.id)
      setStep("callitem")
      toast.success("Commitment added", { description: investor.name })
    } catch {
      // Non-401 errors surface through the api client's toast middleware.
    }
  }

  function finish(candidate: MatchCandidate | null) {
    onCompleted?.(candidate)
    onOpenChange(false)
  }

  async function handleCreateItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!investor || !commitmentId || !callId || createItems.isPending) return
    const call = (callsQuery.data ?? []).find((c) => c.id === callId)
    if (!call) return
    try {
      const items = await createItems.mutateAsync({
        params: { path: { call_id: callId } },
        body: {
          items: [
            {
              commitment_id: commitmentId,
              amount_due: toNumber(allocationAmount).toFixed(2),
            },
          ],
        },
      })
      const item = items[0]
      queryClient.invalidateQueries({ queryKey: ["/capital-calls"] })
      const candidate: MatchCandidate = {
        capital_call_item_id: item.id,
        capital_call_id: call.id,
        capital_call_title: call.title,
        fund_id: call.fund.id,
        fund_name: call.fund.name,
        currency_code: call.fund.currency_code,
        investor_id: investor.id,
        investor_name: investor.name,
        amount_due: item.amount_due,
        amount_paid: item.amount_paid,
        remaining: (
          toNumber(item.amount_due) - toNumber(item.amount_paid)
        ).toFixed(2),
        score: 1,
        confidence: "high",
        currency_mismatch: Boolean(
          currency &&
            currency.toUpperCase() !== call.fund.currency_code.toUpperCase(),
        ),
      }
      toast.success("Allocated to capital call", { description: call.title })
      finish(candidate)
    } catch {
      // Non-401 errors surface through the api client's toast middleware.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {step === "investor" && (
          <>
            <DialogHeader>
              <DialogTitle className="es-display text-[24px]">
                Add payer as investor
              </DialogTitle>
              <DialogDescription>
                Step 1 of 3 — create the investor record.
              </DialogDescription>
            </DialogHeader>
            <form
              onSubmit={handleCreateInvestor}
              className="flex flex-col gap-3"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="payer-investor-name">Name</Label>
                <Input
                  id="payer-investor-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="payer-investor-code">
                  Investor code (optional)
                </Label>
                <Input
                  id="payer-investor-code"
                  value={investorCode}
                  onChange={(event) => setInvestorCode(event.target.value)}
                  placeholder="e.g. ACME-01"
                />
              </div>
              {iban && (
                <p className="font-sans text-xs text-ink-500">
                  IBAN {iban} will be saved to the investor's notes.
                </p>
              )}
              <DialogFooter>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  disabled={createInvestor.isPending}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={createInvestor.isPending || !name.trim()}
                >
                  {createInvestor.isPending && (
                    <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                  )}
                  Continue
                </Button>
              </DialogFooter>
            </form>
          </>
        )}

        {step === "commitment" && (
          <>
            <DialogHeader>
              <DialogTitle className="es-display text-[24px]">
                Add a commitment
              </DialogTitle>
              <DialogDescription>
                Step 2 of 3 — commit {investor?.name} to a fund.
              </DialogDescription>
            </DialogHeader>
            <form
              onSubmit={handleCreateCommitment}
              className="flex flex-col gap-3"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="commitment-fund">Fund</Label>
                <Select value={fundId} onValueChange={setFundId}>
                  <SelectTrigger id="commitment-fund" className="w-full">
                    <SelectValue placeholder="Select a fund" />
                  </SelectTrigger>
                  <SelectContent>
                    {(fundsQuery.data ?? []).map((fund) => (
                      <SelectItem key={fund.id} value={String(fund.id)}>
                        {fund.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="commitment-amount">Committed amount</Label>
                  <Input
                    id="commitment-amount"
                    value={committedAmount}
                    inputMode="decimal"
                    onChange={(event) => setCommittedAmount(event.target.value)}
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
              <div className="flex flex-col gap-2">
                <Label htmlFor="commitment-status">Status</Label>
                <Select
                  value={status}
                  onValueChange={(value) =>
                    setStatus(value as CommitmentStatus)
                  }
                >
                  <SelectTrigger id="commitment-status" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => finish(null)}
                  disabled={createCommitment.isPending}
                >
                  Skip
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={
                    createCommitment.isPending ||
                    !fundId ||
                    toNumber(committedAmount) <= 0
                  }
                >
                  {createCommitment.isPending && (
                    <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                  )}
                  Continue
                </Button>
              </DialogFooter>
            </form>
          </>
        )}

        {step === "callitem" && (
          <>
            <DialogHeader>
              <DialogTitle className="es-display text-[24px]">
                Allocate to a capital call
              </DialogTitle>
              <DialogDescription>
                Step 3 of 3 — add {investor?.name} to a capital call so this
                payment can settle it.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateItem} className="flex flex-col gap-3">
              <div className="flex flex-col gap-2">
                <Label htmlFor="allocation-call">Capital call</Label>
                <Select value={callId} onValueChange={setCallId}>
                  <SelectTrigger id="allocation-call" className="w-full">
                    <SelectValue
                      placeholder={
                        callsQuery.isLoading
                          ? "Loading…"
                          : "Select a capital call"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {(callsQuery.data ?? []).map((call) => (
                      <SelectItem key={call.id} value={String(call.id)}>
                        {call.title} · {call.status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!callsQuery.isLoading &&
                  (callsQuery.data ?? []).length === 0 && (
                    <p className="font-sans text-xs text-ink-500">
                      This fund has no capital calls yet. Create one first, then
                      re-import — or skip for now.
                    </p>
                  )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="allocation-amount">Amount due</Label>
                <Input
                  id="allocation-amount"
                  value={allocationAmount}
                  inputMode="decimal"
                  onChange={(event) => setAllocationAmount(event.target.value)}
                  required
                />
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => finish(null)}
                  disabled={createItems.isPending}
                >
                  Skip
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={
                    createItems.isPending ||
                    !callId ||
                    toNumber(allocationAmount) <= 0
                  }
                >
                  {createItems.isPending && (
                    <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                  )}
                  Allocate & finish
                </Button>
              </DialogFooter>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
