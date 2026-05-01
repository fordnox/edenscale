import { useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Input } from "@/components/ui/input"
import { ProgressBar } from "@/components/ui/progress"
import { StatusPill } from "@/components/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { formatCurrency, formatDate } from "@/lib/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

interface DistributionDetailProps {
  distributionId: number
}

export function DistributionDetail({ distributionId }: DistributionDetailProps) {
  const queryClient = useQueryClient()

  const distributionQuery = useApiQuery(
    "/distributions/{distribution_id}",
    { params: { path: { distribution_id: distributionId } } },
  )
  const fundId = distributionQuery.data?.fund_id ?? null

  const commitmentsQuery = useApiQuery(
    "/funds/{fund_id}/commitments",
    fundId !== null
      ? { params: { path: { fund_id: fundId } } }
      : ({ params: { path: { fund_id: 0 } } } as never),
    { enabled: fundId !== null },
  )

  const investorByCommitment = useMemo(() => {
    const map = new Map<number, { id: number; name: string }>()
    for (const c of commitmentsQuery.data ?? []) {
      map.set(c.id, { id: c.investor.id, name: c.investor.name })
    }
    return map
  }, [commitmentsQuery.data])

  function invalidateDistributionScopes() {
    queryClient.invalidateQueries({ queryKey: ["/distributions"] })
    queryClient.invalidateQueries({
      queryKey: [
        "/distributions/{distribution_id}",
        { params: { path: { distribution_id: distributionId } } },
      ],
    })
    if (fundId !== null) {
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/distributions",
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

  const sendDistribution = useApiMutation(
    "post",
    "/distributions/{distribution_id}/send",
    {
      onSuccess: () => {
        toast.success("Distribution sent")
        invalidateDistributionScopes()
      },
    },
  )
  const cancelDistribution = useApiMutation(
    "post",
    "/distributions/{distribution_id}/cancel",
    {
      onSuccess: () => {
        toast.success("Distribution cancelled")
        invalidateDistributionScopes()
      },
    },
  )
  const updateItem = useApiMutation(
    "patch",
    "/distributions/{distribution_id}/items/{item_id}",
    {
      onSuccess: () => {
        toast.success("Payment recorded")
        invalidateDistributionScopes()
      },
    },
  )

  const [paymentDrafts, setPaymentDrafts] = useState<Record<number, string>>({})

  if (distributionQuery.isLoading || !distributionQuery.data) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
      </div>
    )
  }

  const distribution = distributionQuery.data
  const items = distribution.items ?? []
  const currency = distribution.fund.currency_code
  const amountTotal = parseDecimal(distribution.amount)
  const paidTotal = items.reduce(
    (acc, i) => acc + parseDecimal(i.amount_paid),
    0,
  )
  const dueTotal = items.reduce(
    (acc, i) => acc + parseDecimal(i.amount_due),
    0,
  )
  const paidPct = amountTotal > 0 ? Math.min(paidTotal / amountTotal, 1) : 0

  const canSend =
    distribution.status === "draft" || distribution.status === "scheduled"
  const canCancel = !["paid", "cancelled"].includes(distribution.status)

  function handleRecordPayment(itemId: number) {
    const draft = paymentDrafts[itemId]
    if (draft === undefined || draft.trim() === "") return
    const numeric = Number(draft)
    if (!Number.isFinite(numeric) || numeric < 0) return
    updateItem.mutate(
      {
        params: {
          path: { distribution_id: distributionId, item_id: itemId },
        },
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
        <Eyebrow>{distribution.fund.name}</Eyebrow>
        <h2 className="es-display mt-2 text-[22px] leading-tight md:text-[28px]">
          {distribution.title}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-3 font-sans text-[12px] text-ink-500">
          <StatusPill kind="distribution" value={distribution.status} />
          <span>Distributed {formatDate(distribution.distribution_date)}</span>
          {distribution.record_date && (
            <span>· Record {formatDate(distribution.record_date)}</span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {distribution.description && (
          <div className="border-b border-[color:var(--border-hairline)] px-6 py-4">
            <p className="max-w-full break-words font-sans text-[13px] leading-[1.55] text-ink-700">
              {distribution.description}
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
            <Eyebrow>Paid</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {formatCurrency(paidTotal, currency, { compact: true })}
            </span>
            <ProgressBar value={paidPct} tone="brand" />
          </div>
          <div className="flex flex-col gap-1">
            <Eyebrow>Allocated</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {formatCurrency(dueTotal, currency, { compact: true })}
            </span>
            <span className="font-sans text-[11px] text-ink-500">
              {items.length} limited partners
            </span>
          </div>
        </div>

        <div className="px-6 pb-6 pt-5">
          <Eyebrow>Allocations</Eyebrow>
          {items.length === 0 ? (
            <div className="mt-4 flex flex-col items-start gap-2 border border-dashed border-[color:var(--border-hairline)] p-6">
              <p className="font-sans text-[13px] text-ink-700">
                No items allocated yet. Items can be added pro-rata when the
                distribution is created, or manually via the API.
              </p>
            </div>
          ) : (
            <DataTable className="mt-3">
            <thead>
              <tr>
                <TH>Investor</TH>
                <TH align="right">Due</TH>
                <TH align="right">Paid</TH>
                <TH align="right">Record payment</TH>
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
                        <span>
                          {investor?.name ??
                            `Commitment #${item.commitment_id}`}
                        </span>
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
                  </TR>
                )
              })}
            </tbody>
          </DataTable>
          )}
        </div>
      </div>

      <div className="sticky bottom-0 z-10 border-t border-[color:var(--border-hairline)] bg-surface px-6 py-3">
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="secondary"
            size="sm"
            className="min-h-11 w-full md:min-h-9 md:w-auto"
            disabled={!canCancel || cancelDistribution.isPending}
            onClick={() =>
              cancelDistribution.mutate({
                params: { path: { distribution_id: distributionId } },
              })
            }
          >
            {cancelDistribution.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            className="min-h-11 w-full md:min-h-9 md:w-auto"
            disabled={
              !canSend || sendDistribution.isPending || items.length === 0
            }
            onClick={() =>
              sendDistribution.mutate({
                params: { path: { distribution_id: distributionId } },
              })
            }
          >
            {sendDistribution.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Send
          </Button>
        </div>
      </div>
    </div>
  )
}
