import { useEffect, useMemo, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { formatDate, titleCase } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type CommunicationType = components["schemas"]["CommunicationType"]

const TYPE_TONE: Record<
  CommunicationType,
  React.ComponentProps<typeof Badge>["tone"]
> = {
  announcement: "info",
  message: "active",
  notification: "warning",
}

function formatTimestamp(value: string | null) {
  if (!value) return null
  return formatDate(value, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

interface LetterDetailProps {
  letterId: string
  canSend: boolean
}

export function LetterDetail({ letterId, canSend }: LetterDetailProps) {
  const queryClient = useQueryClient()

  const letterQuery = useApiQuery("/communications/{communication_id}", {
    params: { path: { communication_id: letterId } },
  })
  const fundsQuery = useApiQuery("/funds")
  // The org user directory is manager-only on the backend; LPs resolve
  // recipients to a generic label instead.
  const usersQuery = useApiQuery("/users", undefined, { enabled: canSend })
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const fundName = useMemo(() => {
    const id = letterQuery.data?.fund_id
    if (id === null || id === undefined) return null
    const match = (fundsQuery.data ?? []).find((f) => f.id === id)
    return match?.name ?? `Fund #${id}`
  }, [letterQuery.data?.fund_id, fundsQuery.data])

  const userById = useMemo(() => {
    const map = new Map<string, { name: string; email: string }>()
    for (const u of usersQuery.data ?? []) {
      const name = `${u.first_name} ${u.last_name}`.trim() || u.email
      map.set(u.id, { name, email: u.email })
    }
    return map
  }, [usersQuery.data])

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["/communications"] })
    queryClient.invalidateQueries({
      queryKey: [
        "/communications/{communication_id}",
        { params: { path: { communication_id: letterId } } },
      ],
    })
    if (letterQuery.data?.fund_id !== null && letterQuery.data?.fund_id !== undefined) {
      queryClient.invalidateQueries({
        queryKey: [
          "/funds/{fund_id}/communications",
          {
            params: { path: { fund_id: letterQuery.data.fund_id } },
          },
        ],
      })
    }
  }

  const sendLetter = useApiMutation(
    "post",
    "/communications/{communication_id}/send",
    {
      onSuccess: () => {
        toast.success("Letter sent")
        invalidate()
      },
    },
  )
  const markRead = useApiMutation(
    "post",
    "/communications/{communication_id}/recipients/{recipient_id}/read",
    {
      onSuccess: () => invalidate(),
    },
  )

  // Record the reader's receipt the first time they open a sent letter.
  const receiptFiredRef = useRef(false)
  const myUnreadRecipientId = useMemo(() => {
    const me = meQuery.data
    const letter = letterQuery.data
    if (!me || !letter || letter.sent_at === null) return null
    const mine = (letter.recipients ?? []).find(
      (r) => r.user_id === me.id && r.read_at === null,
    )
    return mine?.id ?? null
  }, [meQuery.data, letterQuery.data])

  useEffect(() => {
    if (myUnreadRecipientId === null || receiptFiredRef.current) return
    receiptFiredRef.current = true
    markRead.mutate({
      params: {
        path: {
          communication_id: letterId,
          recipient_id: myUnreadRecipientId,
        },
      },
    })
    // markRead is stable enough for this fire-once effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myUnreadRecipientId, letterId])

  if (letterQuery.isLoading || !letterQuery.data) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
      </div>
    )
  }

  const letter = letterQuery.data
  const recipients = letter.recipients ?? []
  const readCount = recipients.filter((r) => r.read_at !== null).length
  const deliveredCount = recipients.filter((r) => r.delivered_at !== null).length
  const readPct = recipients.length > 0 ? readCount / recipients.length : 0
  const isDraft = letter.sent_at === null
  const showSend = isDraft && canSend

  function recipientLabel(
    recipient: components["schemas"]["CommunicationRecipientRead"],
  ) {
    if (recipient.user_id !== null) {
      const u = userById.get(recipient.user_id)
      if (u) return { name: u.name, secondary: u.email }
      return { name: "Recipient", secondary: null }
    }
    if (recipient.investor_contact_id !== null) {
      return {
        name: `Contact #${recipient.investor_contact_id}`,
        secondary: "Investor contact",
      }
    }
    return { name: "Unknown", secondary: null }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="sticky top-0 z-10 border-b border-[color:var(--border-hairline)] bg-surface px-6 py-3">
        <Eyebrow>{fundName ?? "Firm-wide"}</Eyebrow>
        <h2 className="es-display mt-2 text-[22px] leading-tight md:text-[28px]">
          {letter.subject}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-3 font-sans text-[12px] text-ink-500">
          <Badge tone={TYPE_TONE[letter.type]}>{titleCase(letter.type)}</Badge>
          {letter.sent_at ? (
            <span>Sent {formatTimestamp(letter.sent_at)}</span>
          ) : (
            <Badge tone="draft">Draft</Badge>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {canSend && (
        <div className="grid grid-cols-3 gap-4 border-b border-[color:var(--border-hairline)] px-6 py-5">
          <div className="flex flex-col gap-1">
            <Eyebrow>Recipients</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {recipients.length}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <Eyebrow>Delivered</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {deliveredCount}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <Eyebrow>Read</Eyebrow>
            <span className="es-numeric font-display text-[22px] text-ink-900">
              {Math.round(readPct * 100)}%
            </span>
            <ProgressBar value={readPct} tone="brand" />
          </div>
        </div>
        )}

        <div className="border-b border-[color:var(--border-hairline)] px-6 py-5">
          <Eyebrow>Body</Eyebrow>
          <p className="mt-3 max-w-full whitespace-pre-wrap break-words font-sans text-[14px] leading-[1.65] text-ink-700">
            {letter.body}
          </p>
        </div>

        {canSend && (
        <div className="px-6 pb-6 pt-5">
          <Eyebrow>Recipients</Eyebrow>
          {recipients.length === 0 ? (
            <div className="mt-4 flex flex-col items-start gap-2 border border-dashed border-[color:var(--border-hairline)] p-6">
              <p className="font-sans text-[13px] text-ink-700">
                {isDraft
                  ? "Recipients are picked up automatically when the letter is sent."
                  : "No recipients on record."}
              </p>
            </div>
          ) : (
            <DataTable className="mt-3">
              <thead>
                <tr>
                  <TH>Recipient</TH>
                  <TH align="right">Delivered</TH>
                  <TH align="right">Read</TH>
                </tr>
              </thead>
              <tbody>
                {recipients.map((recipient) => {
                  const label = recipientLabel(recipient)
                  return (
                    <TR key={recipient.id}>
                      <TD primary>
                        <div className="flex flex-col gap-1">
                          <span>{label.name}</span>
                          {label.secondary && (
                            <span className="font-sans text-[11px] font-normal text-ink-500">
                              {label.secondary}
                            </span>
                          )}
                        </div>
                      </TD>
                      <TD align="right">
                        {formatTimestamp(recipient.delivered_at) ?? (
                          <span className="text-ink-500">—</span>
                        )}
                      </TD>
                      <TD align="right">
                        {recipient.read_at ? (
                          formatTimestamp(recipient.read_at)
                        ) : (
                          <span className="text-ink-500">—</span>
                        )}
                      </TD>
                    </TR>
                  )
                })}
              </tbody>
            </DataTable>
          )}
        </div>
        )}
      </div>

      {showSend && (
        <div className="sticky bottom-0 z-10 border-t border-[color:var(--border-hairline)] bg-surface px-6 py-3">
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={sendLetter.isPending}
              onClick={() =>
                sendLetter.mutate({
                  params: { path: { communication_id: letterId } },
                  body: null,
                })
              }
            >
              {sendLetter.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Send now
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
