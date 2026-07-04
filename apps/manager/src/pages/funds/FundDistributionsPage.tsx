import { useState } from "react"
import { Loader2 } from "lucide-react"

import { DistributionCreateDialog } from "@/components/distributions/DistributionCreateDialog"
import { DistributionDetail } from "@/components/distributions/DistributionDetail"
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

export default function FundDistributionsPage() {
  const { fund, canManage } = useFundContext()
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedDistributionId, setSelectedDistributionId] = useState<
    string | null
  >(null)

  const distributionsQuery = useApiQuery("/funds/{fund_id}/distributions", {
    params: { path: { fund_id: fund.id } },
  })
  const distributions = distributionsQuery.data ?? []

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <Eyebrow>Distributions ({distributions.length})</Eyebrow>
        {canManage && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            New distribution
          </Button>
        )}
      </div>
      <Card>
        <CardSection className="pt-4">
          {distributionsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : distributions.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-4">
              <Eyebrow>No distributions yet</Eyebrow>
              <p className="font-sans text-[14px] text-ink-700">
                Distributions issued to limited partners will appear here.
              </p>
              {canManage && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => setCreateOpen(true)}
                >
                  New distribution
                </Button>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-[color:var(--border-hairline)]">
              {distributions.map((d) => (
                <li
                  key={d.id}
                  className="flex cursor-pointer items-start gap-4 py-4 first:pt-0 last:pb-0"
                  onClick={() => setSelectedDistributionId(d.id)}
                >
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="font-sans text-[14px] font-medium text-ink-900">
                      {d.title}
                    </span>
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                      <span>{formatDate(d.distribution_date)}</span>
                      <span className="size-1 rounded-full bg-ink-300" />
                      <span className="es-numeric">
                        {formatCurrency(parseDecimal(d.amount), fund.currency_code, {
                          compact: true,
                        })}
                      </span>
                    </div>
                  </div>
                  <StatusPill kind="distribution" value={d.status} />
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>

      <DistributionCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultFundId={fund.id}
        onCreated={(id) => setSelectedDistributionId(id)}
      />

      <Sheet
        open={selectedDistributionId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedDistributionId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Distribution detail</SheetTitle>
          <SheetDescription className="sr-only">
            Allocations and actions for the selected distribution.
          </SheetDescription>
          {selectedDistributionId !== null && (
            <DistributionDetail
              key={selectedDistributionId}
              distributionId={selectedDistributionId}
            />
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}
