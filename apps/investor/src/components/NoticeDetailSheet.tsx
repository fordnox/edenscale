import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { formatCurrency, formatDate } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type CapitalCallRead = components["schemas"]["CapitalCallRead"]
type DistributionRead = components["schemas"]["DistributionRead"]

type Notice =
  | { kind: "capital_call"; record: CapitalCallRead }
  | { kind: "distribution"; record: DistributionRead }

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

// Read-only detail for one capital notice / distribution, scoped to the LP's
// own allocation items (the backend already strips others' items).
export function NoticeDetailSheet({
  notice,
  onClose,
}: {
  notice: Notice | null
  onClose: () => void
}) {
  const record = notice?.record
  const items = record?.items ?? []
  const currency = record?.fund.currency_code ?? "USD"
  const due = items.reduce((a, i) => a + parseDecimal(i.amount_due), 0)
  const paid = items.reduce((a, i) => a + parseDecimal(i.amount_paid), 0)
  const isCall = notice?.kind === "capital_call"
  const label = isCall ? "Capital call" : "Distribution"

  return (
    <Sheet open={notice !== null} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
      >
        <SheetTitle className="sr-only">{label} detail</SheetTitle>
        <SheetDescription className="sr-only">
          Your allocation for the selected {label.toLowerCase()}.
        </SheetDescription>
        {notice && record && (
          <div className="flex flex-col gap-6 overflow-y-auto px-6 py-8 md:px-8">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Eyebrow>{label}</Eyebrow>
                <StatusPill kind={notice.kind} value={record.status} />
              </div>
              <h2 className="es-display text-[28px] leading-tight">
                {record.title}
              </h2>
              <span className="font-sans text-[13px] text-ink-500">
                {record.fund.name}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-6 border-y border-[color:var(--border-hairline)] py-5">
              <Stat
                label={isCall ? "Your amount due" : "Your amount"}
                value={formatCurrency(due, currency, { compact: true })}
              />
              <Stat
                label={isCall ? "Paid" : "Received"}
                value={formatCurrency(paid, currency, { compact: true })}
                caption={due > 0 ? `${Math.round((paid / due) * 100)}%` : undefined}
              />
            </div>

            <div className="flex flex-col gap-3">
              <Eyebrow>Details</Eyebrow>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 font-sans text-[13px]">
                {isCall ? (
                  <>
                    <MetaRow
                      label="Due date"
                      value={formatDate((record as CapitalCallRead).due_date)}
                    />
                    <MetaRow
                      label="Call date"
                      value={
                        (record as CapitalCallRead).call_date
                          ? formatDate((record as CapitalCallRead).call_date!)
                          : "—"
                      }
                    />
                  </>
                ) : (
                  <>
                    <MetaRow
                      label="Payment date"
                      value={formatDate(
                        (record as DistributionRead).distribution_date,
                      )}
                    />
                    <MetaRow
                      label="Record date"
                      value={
                        (record as DistributionRead).record_date
                          ? formatDate((record as DistributionRead).record_date!)
                          : "—"
                      }
                    />
                  </>
                )}
              </dl>
              {record.description && (
                <p className="mt-2 whitespace-pre-wrap font-sans text-[14px] leading-[1.6] text-ink-700">
                  {record.description}
                </p>
              )}
            </div>

            {items.length > 0 && (
              <div className="flex flex-col gap-3">
                <Eyebrow>Your allocation</Eyebrow>
                <DataTable>
                  <thead>
                    <tr>
                      <TH align="right">Amount</TH>
                      <TH align="right">{isCall ? "Paid" : "Received"}</TH>
                      <TH align="right">{isCall ? "Paid on" : "Paid on"}</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <TR key={item.id}>
                        <TD align="right" primary>
                          {formatCurrency(parseDecimal(item.amount_due), currency)}
                        </TD>
                        <TD align="right">
                          {formatCurrency(parseDecimal(item.amount_paid), currency)}
                        </TD>
                        <TD align="right">
                          {item.paid_at ? formatDate(item.paid_at) : "—"}
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </DataTable>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="font-sans text-[11px] tracking-[0.04em] text-ink-500 uppercase">
        {label}
      </dt>
      <dd className="font-sans text-[14px] text-ink-900">{value}</dd>
    </div>
  )
}
