import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@edenscale/ui/dialog"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { formatCurrency, formatDate } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

// NAV marks for a fund — latest drives TVPI/RVPI and the LP fair-value figures.
export function FundValuationsCard({
  fundId,
  currency,
  canManage,
}: {
  fundId: string
  currency: string
  canManage: boolean
}) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [asOfDate, setAsOfDate] = useState("")
  const [nav, setNav] = useState("")

  // The backend now paginates this route (default limit 100). NAV marks are
  // usually monthly or quarterly, but a long-lived fund marked frequently
  // could exceed the default — request an explicit, generous limit rather
  // than silently truncating this card's history.
  const valuationsQuery = useApiQuery("/funds/{fund_id}/valuations", {
    params: { path: { fund_id: fundId }, query: { limit: 500 } },
  })
  const valuations = valuationsQuery.data ?? []

  const create = useApiMutation("post", "/funds/{fund_id}/valuations")
  const remove = useApiMutation(
    "delete",
    "/funds/{fund_id}/valuations/{valuation_id}",
  )

  function invalidate() {
    queryClient.invalidateQueries({
      queryKey: ["/funds/{fund_id}/valuations"],
    })
    queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}/overview"] })
    queryClient.invalidateQueries({ queryKey: ["/funds"] })
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!asOfDate || !nav.trim() || create.isPending) return
    try {
      await create.mutateAsync({
        params: { path: { fund_id: fundId } },
        body: { as_of_date: asOfDate, nav: nav.trim() },
      })
      toast.success("Valuation recorded")
      setOpen(false)
      setAsOfDate("")
      setNav("")
      invalidate()
    } catch {
      // useApiMutation surfaces a toast
    }
  }

  async function handleDelete(valuationId: string) {
    try {
      await remove.mutateAsync({
        params: { path: { fund_id: fundId, valuation_id: valuationId } },
      })
      toast.success("Valuation removed")
      invalidate()
    } catch {
      // useApiMutation surfaces a toast
    }
  }

  return (
    <Card>
      <CardSection>
        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <Eyebrow>Fund NAV history</Eyebrow>
            <p className="font-sans text-[13px] text-ink-500">
              The latest mark drives TVPI, RVPI, and each LP's fair value.
            </p>
          </div>
          {canManage && (
            <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
              <Plus strokeWidth={1.5} className="size-4" />
              Record NAV
            </Button>
          )}
        </div>

        <div className="mt-5">
          {valuationsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : valuations.length === 0 ? (
            <EmptyState
              title="No valuations yet"
              body={
                canManage
                  ? "Record a fund NAV to enable fair-value reporting."
                  : "This fund has not been marked yet."
              }
            />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>As of</TH>
                  <TH align="right">NAV</TH>
                  <TH>Note</TH>
                  {canManage && <TH align="right"> </TH>}
                </tr>
              </thead>
              <tbody>
                {valuations.map((v) => (
                  <TR key={v.id}>
                    <TD primary>{formatDate(v.as_of_date)}</TD>
                    <TD align="right">
                      {formatCurrency(parseDecimal(v.nav), currency, {
                        compact: false,
                      })}
                    </TD>
                    <TD>{v.note ?? "—"}</TD>
                    {canManage && (
                      <TD align="right">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Delete valuation"
                          disabled={remove.isPending}
                          onClick={() => handleDelete(v.id)}
                        >
                          <Trash2 strokeWidth={1.5} className="size-4 text-ink-500" />
                        </Button>
                      </TD>
                    )}
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </div>
      </CardSection>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record fund NAV</DialogTitle>
            <DialogDescription>
              Enter the fund's net asset value (fair value) as of a date. A mark
              for an existing date overwrites it.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="valuation-date">As of date</Label>
              <Input
                id="valuation-date"
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="valuation-nav">NAV ({currency})</Label>
              <Input
                id="valuation-nav"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={nav}
                onChange={(e) => setNav(e.target.value)}
                placeholder="e.g. 50000000"
                required
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={create.isPending}
              >
                {create.isPending && (
                  <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                )}
                Save valuation
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
