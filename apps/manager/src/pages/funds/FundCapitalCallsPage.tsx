import { useState } from "react"
import { Loader2 } from "lucide-react"

import { CapitalCallCreateDialog } from "@/components/capital-calls/CapitalCallCreateDialog"
import { CapitalCallDetail } from "@/components/capital-calls/CapitalCallDetail"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { StatusPill } from "@edenscale/ui/StatusPill"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useFundContext } from "@/layouts/FundLayout"
import { formatCurrency, formatDate } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function FundCapitalCallsPage() {
  const { fund, canManage } = useFundContext()
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)

  const callsQuery = useApiQuery("/funds/{fund_id}/capital-calls", {
    params: { path: { fund_id: fund.id } },
  })
  const calls = callsQuery.data ?? []

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <Eyebrow>Capital calls ({calls.length})</Eyebrow>
        {canManage && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            New capital call
          </Button>
        )}
      </div>
      <Card>
        <CardSection className="pt-4">
          {callsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : calls.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-4">
              <Eyebrow>No capital calls yet</Eyebrow>
              <p className="font-sans text-[14px] text-ink-700">
                When you issue a capital call against this fund, it will appear here.
              </p>
              {canManage && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => setCreateOpen(true)}
                >
                  New capital call
                </Button>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-[color:var(--border-hairline)]">
              {calls.map((c) => (
                <li
                  key={c.id}
                  className="flex cursor-pointer items-start gap-4 py-4 first:pt-0 last:pb-0"
                  onClick={() => setSelectedCallId(c.id)}
                >
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="font-sans text-[14px] font-medium text-ink-900">
                      {c.title}
                    </span>
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                      <span>Due {formatDate(c.due_date)}</span>
                      <span className="size-1 rounded-full bg-ink-300" />
                      <span className="es-numeric">
                        {formatCurrency(parseDecimal(c.amount), fund.currency_code, {
                          compact: true,
                        })}
                      </span>
                    </div>
                  </div>
                  <StatusPill kind="capital_call" value={c.status} />
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>

      <CapitalCallCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultFundId={fund.id}
        onCreated={(id) => setSelectedCallId(id)}
      />

      <Sheet
        open={selectedCallId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedCallId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Capital call detail</SheetTitle>
          <SheetDescription className="sr-only">
            Allocations and actions for the selected capital call.
          </SheetDescription>
          {selectedCallId !== null && (
            <CapitalCallDetail key={selectedCallId} callId={selectedCallId} />
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}
