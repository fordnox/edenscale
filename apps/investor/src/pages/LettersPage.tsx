import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, Mail } from "lucide-react"

import api from "@edenscale/api/client"

import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { EmptyState } from "@edenscale/ui/EmptyState"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatDate, titleCase } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type CommunicationRead = components["schemas"]["CommunicationRead"]
type CommunicationRecipientRead = components["schemas"]["CommunicationRecipientRead"]

export default function LettersPage() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const lettersQuery = useApiQuery("/communications")
  const letters = useMemo(() => lettersQuery.data ?? [], [lettersQuery.data])

  const meQuery = useApiQuery("/users/me", undefined, { staleTime: 5 * 60 * 1000 })
  const myUserId = meQuery.data?.id ?? null

  // For LPs, /investors returns only their own investor(s) and
  // /investors/{id}/contacts returns only their own contact rows — so every
  // contact id we collect here belongs to the current user. Used to find the
  // recipient row that is "theirs" when it's linked by contact rather than
  // user_id (letters sent before the LP claimed their contact carry only an
  // investor_contact_id). An LP can be a contact on more than one investor, so
  // we gather contacts across all of them, not just the first.
  const investorsQuery = useApiQuery("/investors")
  const investorIds = useMemo(
    () => (investorsQuery.data ?? []).map((i) => i.id),
    [investorsQuery.data],
  )
  const contactsQuery = useQuery({
    queryKey: ["/investors/contacts/mine", investorIds],
    enabled: investorIds.length > 0,
    queryFn: async () => {
      const results = await Promise.all(
        investorIds.map((id) =>
          api.GET("/investors/{investor_id}/contacts", {
            params: { path: { investor_id: id } },
          }),
        ),
      )
      return results.flatMap(({ data }) => (data ?? []).map((c) => c.id))
    },
  })
  const myContactIds = useMemo(
    () => new Set(contactsQuery.data ?? []),
    [contactsQuery.data],
  )

  function myRecipient(
    letter: CommunicationRead | undefined,
  ): CommunicationRecipientRead | null {
    if (!letter) return null
    return (
      letter.recipients.find(
        (r) =>
          (myUserId != null && r.user_id === myUserId) ||
          (r.investor_contact_id != null && myContactIds.has(r.investor_contact_id)),
      ) ?? null
    )
  }

  const selected = useMemo(
    () => letters.find((l) => l.id === selectedId),
    [letters, selectedId],
  )

  const markRead = useApiMutation(
    "post",
    "/communications/{communication_id}/recipients/{recipient_id}/read",
  )

  // Mark the LP's own recipient row read when they open an unread letter.
  useEffect(() => {
    if (!selected) return
    const recipient = myRecipient(selected)
    if (!recipient || recipient.read_at) return
    markRead
      .mutateAsync({
        params: {
          path: {
            communication_id: selected.id,
            recipient_id: recipient.id,
          },
        },
      })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ["/communications"] })
        queryClient.invalidateQueries({ queryKey: ["/dashboard/overview"] })
      })
      .catch(() => {
        // useApiMutation surfaces a toast already
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  return (
    <>
      <Helmet>
        <title>{`Letters · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Correspondence"
        title="Letters to you."
        description="Announcements, notices, and messages from your fund managers."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          <CardSection className="pt-2 pb-0">
            {lettersQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : letters.length === 0 ? (
              <EmptyState
                icon={<Mail strokeWidth={1.25} />}
                title="No letters"
                body="No correspondence has been shared with you yet."
              />
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Subject</TH>
                    <TH align="right">Type</TH>
                    <TH align="right">Sent</TH>
                    <TH align="right">Status</TH>
                  </tr>
                </thead>
                <tbody>
                  {letters.map((letter) => {
                    const recipient = myRecipient(letter)
                    const isUnread = recipient != null && !recipient.read_at
                    return (
                      <TR
                        key={letter.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(letter.id)}
                      >
                        <TD primary>
                          <span
                            className={isUnread ? "font-semibold" : undefined}
                          >
                            {letter.subject}
                          </span>
                        </TD>
                        <TD align="right">{titleCase(letter.type)}</TD>
                        <TD align="right">
                          {letter.sent_at ? formatDate(letter.sent_at) : "—"}
                        </TD>
                        <TD align="right">
                          <span
                            className={
                              isUnread
                                ? "font-sans text-[12px] font-medium text-brass-700"
                                : "font-sans text-[12px] text-ink-500"
                            }
                          >
                            {recipient == null
                              ? "—"
                              : isUnread
                                ? "Unread"
                                : "Read"}
                          </span>
                        </TD>
                      </TR>
                    )
                  })}
                </tbody>
              </DataTable>
            )}
          </CardSection>
        </Card>
      </div>

      <Sheet
        open={selectedId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Letter</SheetTitle>
          <SheetDescription className="sr-only">
            The full text of the selected letter.
          </SheetDescription>
          {selected && (
            <div className="flex flex-col gap-6 overflow-y-auto px-6 py-8 md:px-8">
              <div className="flex flex-col gap-3">
                <Eyebrow>{titleCase(selected.type)}</Eyebrow>
                <h2 className="es-display text-[28px] leading-tight">
                  {selected.subject}
                </h2>
                <span className="font-sans text-[12px] text-ink-500">
                  {selected.sent_at
                    ? `Sent ${formatDate(selected.sent_at)}`
                    : "Draft"}
                </span>
              </div>
              <hr className="es-rule" />
              <div className="whitespace-pre-wrap font-sans text-[15px] leading-[1.6] text-ink-800">
                {selected.body}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}
