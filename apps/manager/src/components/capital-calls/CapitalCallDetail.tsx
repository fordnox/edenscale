import { useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import { ProgressBar } from "@edenscale/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { formatCurrency, formatDate } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

interface CapitalCallDetailProps {
  callId: string
}

export function CapitalCallDetail({ callId }: CapitalCallDetailProps) {
  const queryClient = useQueryClient()
  const { activeMembership, isSuperadmin } = useActiveOrganization()
  const canManage =
    isSuperadmin ||
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  const callQuery = useApiQuery("/capital-calls/{call_id}", {
    params: { path: { call_id: callId } },
  })
  const fundId = callQuery.data?.fund_id ?? null

  const commitmentsQuery = useApiQuery(
    "/funds/{fund_id}/commitments",
    fundId !== null
      ? { params: { path: { fund_id: fundId } } }
      : ({ params: { path: { fund_id: "" } } } as never),
    { enabled: fundId !== null },
  )

  const investorByCommitment = useMemo(() => {
    const map = new Map<string, { id: string; name: string }>()
    for (const c of commitmentsQuery.data ?? []) {
      map.set(c.id, { id: c.investor.id, name: c.investor.name })
    }
    return map
  }, [commitmentsQuery.data])

  function invalidateCallScopes() {
    queryClient.invalidateQueries({ queryKey: ["/capital-calls"] })
    queryClient.invalidateQueries({
      queryKey: [
        "/capital-calls/{call_id}",
        { params: { path: { call_id: callId } } },
      ],
    })
    if (fundId !== null) {
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/capital-calls",
          { params: { path: { fund_id: fundId } } },
        ],
      })
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}",
          { params: { path: { fund_id: fundId } } },
        ],
      })
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/overview",
          { params: { path: { fund_id: fundId } } },
        ],
      })
    }
    queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
  }

  const sendCall = useApiMutation("post", "/capital-calls/{call_id}/send", {
    onSuccess: () => {
      toast.success("Capital call sent")
      invalidateCallScopes()
    },
  })
  const cancelCall = useApiMutation("post", "/capital-calls/{call_id}/cancel", {
    onSuccess: () => {
      toast.success("Capital call cancelled")
      invalidateCallScopes()
    },
  })
  const updateItem = useApiMutation(
    "patch",
    "/capital-calls/{call_id}/items/{item_id}",
    {
      onSuccess: () => {
        toast.success("Payment recorded")
        invalidateCallScopes()
      },
    },
  )
  const addItems = useApiMutation("post", "/capital-calls/{call_id}/items", {
    onSuccess: () => {
      toast.success("Allocations added")
      invalidateCallScopes()
      setAllocationCommitmentId("")
      setAllocationAmount("")
    },
  })

  const [paymentDrafts, setPaymentDrafts] = useState<Record<string, string>>({})
  const [allocationCommitmentId, setAllocationCommitmentId] = useState("")
  const [allocationAmount, setAllocationAmount] = useState("")

  if (callQuery.isLoading || !callQuery.data) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
      </div>
    )
  }

  const call = callQuery.data
  const items = call.items ?? []
  const currency = call.fund.currency_code
  const amountTotal = parseDecimal(call.amount)
  const paidTotal = items.reduce((acc, i) => acc + parseDecimal(i.amount_paid), 0)
  const dueTotal = items.reduce((acc, i) => acc + parseDecimal(i.amount_due), 0)
  // LPs only receive their own allocation items, so progress is measured
  // against their share, not the fund-level call amount.
  const paidPct = canManage
    ? amountTotal > 0
      ? Math.min(paidTotal / amountTotal, 1)
      : 0
    : dueTotal > 0
      ? Math.min(paidTotal / dueTotal, 1)
      : 0

  const canSend =
    canManage && (call.status === "draft" || call.status === "scheduled")
  const canCancel = canManage && !["paid", "cancelled"].includes(call.status)
  const canAllocate = canManage && !["paid", "cancelled"].includes(call.status)

  const allocatedCommitmentIds = new Set(items.map((i) => i.commitment_id))
  const unallocatedCommitments = (commitmentsQuery.data ?? []).filter(
    (c) => !allocatedCommitmentIds.has(c.id),
  )

  function handleRecordPayment(itemId: string) {
    const draft = paymentDrafts[itemId]
    if (draft === undefined || draft.trim() === "") return
    const numeric = Number(draft)
    if (!Number.isFinite(numeric) || numeric < 0) return
    updateItem.mutate(
      {
        params: { path: { call_id: callId, item_id: itemId } },
        body: {
          amount_paid: draft,
          paid_at: new Date().toISOString().slice(0, 10),
        },
      },
      {
        onSuccess: () => {
          setPaymentDrafts((prev) => {
            const next = { ...prev }
            delete next[itemId]
            return next
          })
        },
      },
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="sticky top-0 z-10 border-b border-[color:var(--border-hairline)] bg-surface px-6 py-3">
        <Eyebrow>{call.fund.name}</Eyebrow>
        <h2 className="es-display mt-2 text-[22px] leading-tight md:text-[28px]">
          {call.title}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-3 font-sans text-[12px] text-ink-500">
          <StatusPill kind="capital_call" value={call.status} />
          <span>Due {formatDate(call.due_date)}</span>
          {call.call_date && <span>· Issued {formatDate(call.call_date)}</span>}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {call.description && (
          <div className="border-b border-[color:var(--border-hairline)] px-6 py-4">
            <p className="max-w-full break-words font-sans text-[13px] leading-[1.55] text-ink-700">
              {call.description}
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 border-b border-[color:var(--border-hairline)] px-6 py-5 md:grid-cols-3">
          <div className="flex flex-col gap-1">
            <Eyebrow>Amount</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {formatCurrency(amountTotal, currency, { compact: true })}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <Eyebrow>{canManage ? "Paid" : "You have paid"}</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {formatCurrency(paidTotal, currency, { compact: true })}
            </span>
            <ProgressBar
              value={paidPct}
              tone={call.status === "overdue" ? "brass" : "brand"}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Eyebrow>{canManage ? "Allocated" : "Your share"}</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {formatCurrency(dueTotal, currency, { compact: true })}
            </span>
            <span className="font-sans text-[11px] text-ink-500">
              {canManage
                ? `${items.length} limited partners`
                : `across ${items.length} commitment${items.length === 1 ? "" : "s"}`}
            </span>
          </div>
        </div>

        <div className="px-6 pb-6 pt-5">
          <Eyebrow>Allocations</Eyebrow>
          {items.length === 0 ? (
            <div className="mt-4 flex flex-col items-start gap-3 border border-dashed border-[color:var(--border-hairline)] p-6">
              <p className="font-sans text-[13px] text-ink-700">
                {canAllocate
                  ? "No items allocated yet. Split the call pro-rata across approved commitments, or add allocations one by one below."
                  : "No items allocated yet."}
              </p>
              {canAllocate && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={addItems.isPending}
                  onClick={() =>
                    addItems.mutate({
                      params: {
                        path: { call_id: callId },
                        query: { mode: "pro-rata" },
                      },
                      body: { items: [] },
                    })
                  }
                >
                  {addItems.isPending && (
                    <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                  )}
                  Allocate pro-rata
                </Button>
              )}
            </div>
          ) : (
            <>
              <div className="md:hidden mt-3 flex flex-col gap-3">
                {items.map((item) => {
                  const investor = investorByCommitment.get(item.commitment_id)
                  const due = parseDecimal(item.amount_due)
                  const paid = parseDecimal(item.amount_paid)
                  const fullyPaid = paid >= due && due > 0
                  const draft = paymentDrafts[item.id] ?? ""
                  return (
                    <div
                      key={item.id}
                      className="flex flex-col gap-3 border border-[color:var(--border-hairline)] p-4"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-ink-900 text-[15px] font-semibold tracking-[-0.01em]">
                          {investor?.name ?? `Commitment #${item.commitment_id}`}
                        </span>
                        {fullyPaid && <Badge tone="positive">Paid in full</Badge>}
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="flex flex-col gap-1">
                          <Eyebrow>Due</Eyebrow>
                          <span className="es-numeric font-display text-ink-900 text-[18px]">
                            {formatCurrency(due, currency, { compact: true })}
                          </span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <Eyebrow>Paid</Eyebrow>
                          <span className="es-numeric font-display text-ink-900 text-[18px]">
                            {formatCurrency(paid, currency, { compact: true })}
                          </span>
                        </div>
                      </div>
                      {canManage && (
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            inputMode="decimal"
                            min={0}
                            step="0.01"
                            placeholder={`Record payment (${String(paid)})`}
                            value={draft}
                            onChange={(event) =>
                              setPaymentDrafts((prev) => ({
                                ...prev,
                                [item.id]: event.target.value,
                              }))
                            }
                            className="flex-1"
                          />
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            className="min-h-11"
                            disabled={
                              updateItem.isPending ||
                              draft.trim() === "" ||
                              !Number.isFinite(Number(draft))
                            }
                            onClick={() => handleRecordPayment(item.id)}
                          >
                            Save
                          </Button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
              <div className="hidden md:block">
                <DataTable className="mt-3">
                  <thead>
                    <tr>
                      <TH>Investor</TH>
                      <TH align="right">Due</TH>
                      <TH align="right">Paid</TH>
                      {canManage && <TH align="right">Record payment</TH>}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => {
                      const investor = investorByCommitment.get(item.commitment_id)
                      const due = parseDecimal(item.amount_due)
                      const paid = parseDecimal(item.amount_paid)
                      const fullyPaid = paid >= due && due > 0
                      const draft = paymentDrafts[item.id] ?? ""
                      return (
                        <TR key={item.id}>
                          <TD primary>
                            <div className="flex flex-col gap-1">
                              <span>{investor?.name ?? `Commitment #${item.commitment_id}`}</span>
                              {fullyPaid && (
                                <Badge tone="positive" className="self-start">
                                  Paid in full
                                </Badge>
                              )}
                            </div>
                          </TD>
                          <TD align="right" primary>
                            {formatCurrency(due, currency, { compact: true })}
                          </TD>
                          <TD align="right">
                            {formatCurrency(paid, currency, { compact: true })}
                          </TD>
                          {canManage && (
                            <TD align="right">
                              <div className="flex items-center justify-end gap-2">
                                <Input
                                  type="number"
                                  inputMode="decimal"
                                  min={0}
                                  step="0.01"
                                  placeholder={String(paid)}
                                  value={draft}
                                  onChange={(event) =>
                                    setPaymentDrafts((prev) => ({
                                      ...prev,
                                      [item.id]: event.target.value,
                                    }))
                                  }
                                  className="h-8 w-28 text-right"
                                />
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  disabled={
                                    updateItem.isPending ||
                                    draft.trim() === "" ||
                                    !Number.isFinite(Number(draft))
                                  }
                                  onClick={() => handleRecordPayment(item.id)}
                                >
                                  Save
                                </Button>
                              </div>
                            </TD>
                          )}
                        </TR>
                      )
                    })}
                  </tbody>
                </DataTable>
              </div>
            </>
          )}

          {canAllocate && unallocatedCommitments.length > 0 && (
            <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-[color:var(--border-hairline)] pt-4">
              <div className="flex min-w-[200px] flex-1 flex-col gap-1">
                <Eyebrow>Add allocation</Eyebrow>
                <Select
                  value={allocationCommitmentId}
                  onValueChange={setAllocationCommitmentId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select commitment" />
                  </SelectTrigger>
                  <SelectContent>
                    {unallocatedCommitments.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.investor.name} ·{" "}
                        {formatCurrency(
                          parseDecimal(c.committed_amount),
                          currency,
                          { compact: true },
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Input
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                placeholder="Amount due"
                value={allocationAmount}
                onChange={(event) => setAllocationAmount(event.target.value)}
                className="w-36"
              />
              <Button
                variant="secondary"
                size="sm"
                disabled={
                  addItems.isPending ||
                  allocationCommitmentId === "" ||
                  allocationAmount.trim() === "" ||
                  !Number.isFinite(Number(allocationAmount)) ||
                  Number(allocationAmount) < 0
                }
                onClick={() =>
                  addItems.mutate({
                    params: {
                      path: { call_id: callId },
                      query: { mode: "manual" },
                    },
                    body: {
                      items: [
                        {
                          commitment_id: allocationCommitmentId,
                          amount_due: allocationAmount,
                        },
                      ],
                    },
                  })
                }
              >
                {addItems.isPending && (
                  <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                )}
                Add
              </Button>
            </div>
          )}
        </div>
      </div>

      {canManage && (
      <div className="sticky bottom-0 z-10 border-t border-[color:var(--border-hairline)] bg-surface px-6 py-3">
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="secondary"
            size="sm"
            className="min-h-11 w-full md:min-h-9 md:w-auto"
            disabled={!canCancel || cancelCall.isPending}
            onClick={() =>
              cancelCall.mutate({ params: { path: { call_id: callId } } })
            }
          >
            {cancelCall.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            className="min-h-11 w-full md:min-h-9 md:w-auto"
            disabled={!canSend || sendCall.isPending || items.length === 0}
            onClick={() =>
              sendCall.mutate({ params: { path: { call_id: callId } } })
            }
          >
            {sendCall.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Send
          </Button>
        </div>
      </div>
      )}
    </div>
  )
}
