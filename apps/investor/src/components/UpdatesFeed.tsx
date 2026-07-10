import { useMemo } from "react"
import { Link } from "react-router-dom"
import { ArrowDownToLine, ArrowUpFromLine, Loader2, Mail } from "lucide-react"

import { Card } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { orgPath } from "@/lib/investorRoutes"
import { formatCurrency, formatDate, titleCase } from "@edenscale/shared/format"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

type UpdateKind = "capital_call" | "distribution" | "letter"

interface UpdateItem {
  id: string
  kind: UpdateKind
  label: string
  title: string
  fundName: string | null
  amount: number | null
  currency: string
  paid: boolean | null
  date: string | null
  to: string
}

const ICONS: Record<UpdateKind, typeof Mail> = {
  capital_call: ArrowDownToLine,
  distribution: ArrowUpFromLine,
  letter: Mail,
}

export function UpdatesFeed({
  orgSlug,
  limit = 8,
  archiveLink = false,
}: {
  orgSlug: string | null
  limit?: number
  archiveLink?: boolean
}) {
  const callsQuery = useApiQuery("/investor/capital-calls")
  const distributionsQuery = useApiQuery("/investor/distributions")
  const lettersQuery = useApiQuery("/investor/communications")
  const fundsQuery = useApiQuery("/investor/funds")

  const fundNameById = useMemo(
    () => new Map((fundsQuery.data ?? []).map((f) => [f.id, f.name])),
    [fundsQuery.data],
  )

  const items = useMemo<UpdateItem[]>(() => {
    const out: UpdateItem[] = []

    for (const call of callsQuery.data ?? []) {
      const due = (call.items ?? []).reduce(
        (a, i) => a + parseDecimal(i.amount_due),
        0,
      )
      const paidAmt = (call.items ?? []).reduce(
        (a, i) => a + parseDecimal(i.amount_paid),
        0,
      )
      out.push({
        id: `call-${call.id}`,
        kind: "capital_call",
        label: "Capital notice",
        title: call.title,
        fundName: call.fund.name,
        amount: due,
        currency: call.fund.currency_code,
        paid: due > 0 ? paidAmt >= due : null,
        date: call.call_date ?? call.due_date,
        to: orgSlug ? orgPath(orgSlug, "calls") : "#",
      })
    }

    for (const dist of distributionsQuery.data ?? []) {
      const due = (dist.items ?? []).reduce(
        (a, i) => a + parseDecimal(i.amount_due),
        0,
      )
      const paidAmt = (dist.items ?? []).reduce(
        (a, i) => a + parseDecimal(i.amount_paid),
        0,
      )
      out.push({
        id: `dist-${dist.id}`,
        kind: "distribution",
        label: "Distribution",
        title: dist.title,
        fundName: dist.fund.name,
        amount: due,
        currency: dist.fund.currency_code,
        paid: due > 0 ? paidAmt >= due : null,
        date: dist.distribution_date,
        to: orgSlug ? orgPath(orgSlug, "distributions") : "#",
      })
    }

    for (const letter of lettersQuery.data ?? []) {
      out.push({
        id: `letter-${letter.id}`,
        kind: "letter",
        label: titleCase(letter.type),
        title: letter.subject,
        fundName: letter.fund_id ? (fundNameById.get(letter.fund_id) ?? null) : null,
        amount: null,
        currency: "USD",
        paid: null,
        date: letter.sent_at,
        to: orgSlug ? orgPath(orgSlug, "letters") : "#",
      })
    }

    return out
      .filter((i) => i.date)
      .sort((a, b) => (a.date! < b.date! ? 1 : -1))
      .slice(0, limit)
  }, [
    callsQuery.data,
    distributionsQuery.data,
    lettersQuery.data,
    fundNameById,
    orgSlug,
    limit,
  ])

  const loading =
    callsQuery.isLoading || distributionsQuery.isLoading || lettersQuery.isLoading

  return (
    <section>
      <div className="mb-4 flex items-end justify-between">
        <Eyebrow>Updates</Eyebrow>
        {archiveLink && orgSlug ? (
          <Link
            to={orgPath(orgSlug, "archive")}
            className="font-sans text-[12px] text-conifer-700 underline-offset-4 hover:underline"
          >
            Go to archive
          </Link>
        ) : (
          <span className="font-sans text-[12px] text-ink-500">
            {items.length}
          </span>
        )}
      </div>
      {loading ? (
        <Card>
          <div className="flex min-h-[160px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            title="No updates yet"
            body="Capital notices, distributions, and letters will appear here as they are issued."
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-[color:var(--border-hairline)]">
            {items.map((item) => {
              const Icon = ICONS[item.kind]
              return (
                <li
                  key={item.id}
                  className="flex items-start gap-4 px-6 py-5 md:px-8"
                >
                  <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
                    <Icon strokeWidth={1.5} className="size-4" />
                  </span>
                  <div className="flex flex-1 flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <Eyebrow>{item.label}</Eyebrow>
                      {item.date && (
                        <span className="font-sans text-[11px] text-ink-500">
                          · {formatDate(item.date)}
                        </span>
                      )}
                    </div>
                    <span className="font-sans text-[15px] font-medium text-ink-900">
                      {item.title}
                    </span>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-[12px] text-ink-500">
                      {item.fundName && <span>{item.fundName}</span>}
                      {item.amount != null && item.amount > 0 && (
                        <>
                          <span className="size-1 rounded-full bg-ink-300" />
                          <span className="es-numeric text-ink-900">
                            {formatCurrency(item.amount, item.currency, {
                              compact: true,
                            })}
                          </span>
                        </>
                      )}
                      {item.paid != null && (
                        <span
                          className={
                            item.paid
                              ? "font-medium text-status-positive"
                              : "font-medium text-brass-700"
                          }
                        >
                          {item.paid ? "PAID" : "DUE"}
                        </span>
                      )}
                    </div>
                  </div>
                  <Link
                    to={item.to}
                    className="shrink-0 self-center font-sans text-[13px] text-conifer-700 underline-offset-4 hover:underline"
                  >
                    Details
                  </Link>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </section>
  )
}
