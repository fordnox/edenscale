import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Loader2, Mail } from "lucide-react"

import { LetterComposeDialog } from "@/components/letters/LetterComposeDialog"
import { LetterDetail } from "@/components/letters/LetterDetail"
import { PageHero } from "@/components/layout/PageHero"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { ProgressBar } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatDate, titleCase } from "@/lib/format"
import type { components } from "@/lib/schema"

type CommunicationType = components["schemas"]["CommunicationType"]

const TYPE_OPTIONS: Array<{ value: "all" | CommunicationType; label: string }> = [
  { value: "all", label: "All types" },
  { value: "announcement", label: "Announcement" },
  { value: "message", label: "Message" },
  { value: "notification", label: "Notification" },
]

const TYPE_TONE: Record<
  CommunicationType,
  React.ComponentProps<typeof Badge>["tone"]
> = {
  announcement: "info",
  message: "active",
  notification: "warning",
}

export default function LettersPage() {
  const [composeOpen, setComposeOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [fundFilter, setFundFilter] = useState<"all" | string>("all")
  const [typeFilter, setTypeFilter] = useState<"all" | CommunicationType>("all")

  const fundsQuery = useApiQuery("/funds")
  const lettersQuery = useApiQuery("/communications", {
    params: {
      query: {
        ...(fundFilter !== "all" ? { fund_id: Number(fundFilter) } : {}),
        ...(typeFilter !== "all" ? { type: typeFilter } : {}),
      },
    },
  })

  const letters = useMemo(() => lettersQuery.data ?? [], [lettersQuery.data])

  const fundNameById = useMemo(() => {
    const map = new Map<number, string>()
    for (const f of fundsQuery.data ?? []) map.set(f.id, f.name)
    return map
  }, [fundsQuery.data])

  return (
    <>
      <Helmet>
        <title>{`Letters · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Communications"
        title="What we are thinking, written down."
        description="Quarterly letters and bulletins to limited partners. Read receipts log the moment each recipient opens a note."
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => setComposeOpen(true)}
          >
            New letter
          </Button>
        }
      />

      <div className="px-8 pb-16">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Eyebrow>Type</Eyebrow>
            <Select
              value={typeFilter}
              onValueChange={(value) =>
                setTypeFilter(value as "all" | CommunicationType)
              }
            >
              <SelectTrigger className="min-w-[180px]">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                {TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Eyebrow>Fund</Eyebrow>
            <Select value={fundFilter} onValueChange={setFundFilter}>
              <SelectTrigger className="min-w-[200px]">
                <SelectValue placeholder="All funds" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All funds</SelectItem>
                {(fundsQuery.data ?? []).map((fund) => (
                  <SelectItem key={fund.id} value={String(fund.id)}>
                    {fund.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <span className="ml-auto font-sans text-[12px] text-ink-500">
            {letters.length} letter{letters.length === 1 ? "" : "s"}
          </span>
        </div>

        <Card>
          <CardSection className="pt-2 pb-0">
            {lettersQuery.isLoading ? (
              <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            ) : letters.length === 0 ? (
              <div className="flex flex-col items-start gap-3 py-10">
                <Eyebrow>No letters yet</Eyebrow>
                <p className="max-w-md font-sans text-[14px] leading-[1.55] text-ink-700">
                  Draft a quarterly letter or a quick note to limited partners.
                  Once sent, the read receipts appear here.
                </p>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setComposeOpen(true)}
                >
                  Draft letter
                </Button>
              </div>
            ) : (
              <DataTable>
                <thead>
                  <tr>
                    <TH>Subject</TH>
                    <TH>Type</TH>
                    <TH>Fund</TH>
                    <TH align="right">Sent</TH>
                    <TH align="right">Recipients</TH>
                    <TH align="right">Read</TH>
                  </tr>
                </thead>
                <tbody>
                  {letters.map((letter) => {
                    const recipientCount = letter.recipients.length
                    const readCount = letter.recipients.filter(
                      (r) => r.read_at !== null,
                    ).length
                    const readPct =
                      recipientCount > 0 ? readCount / recipientCount : 0
                    const fundName =
                      letter.fund_id !== null
                        ? (fundNameById.get(letter.fund_id) ??
                          `Fund #${letter.fund_id}`)
                        : null
                    return (
                      <TR
                        key={letter.id}
                        className="cursor-pointer"
                        onClick={() => setSelectedId(letter.id)}
                      >
                        <TD primary>
                          <div className="flex items-start gap-3">
                            <span className="mt-1 inline-flex size-8 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] bg-parchment-100 text-ink-700">
                              <Mail strokeWidth={1.5} className="size-4" />
                            </span>
                            <div className="flex flex-col gap-1">
                              <span>{letter.subject}</span>
                              <span className="font-sans text-[11px] font-normal text-ink-500">
                                {letter.sent_at
                                  ? titleCase(letter.type)
                                  : "Draft"}
                              </span>
                            </div>
                          </div>
                        </TD>
                        <TD>
                          <Badge tone={TYPE_TONE[letter.type]}>
                            {titleCase(letter.type)}
                          </Badge>
                        </TD>
                        <TD>
                          {fundName ?? <span className="text-ink-500">Firm</span>}
                        </TD>
                        <TD align="right">
                          {letter.sent_at ? (
                            formatDate(letter.sent_at)
                          ) : (
                            <span className="text-ink-500">—</span>
                          )}
                        </TD>
                        <TD align="right">{recipientCount}</TD>
                        <TD align="right">
                          {recipientCount === 0 ? (
                            <span className="text-ink-500">—</span>
                          ) : (
                            <div className="flex flex-col items-end gap-1.5">
                              <span className="es-numeric text-[13px] text-ink-900">
                                {Math.round(readPct * 100)}%
                              </span>
                              <ProgressBar
                                value={readPct}
                                className="w-[80px]"
                                tone="brand"
                              />
                            </div>
                          )}
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
          <SheetTitle className="sr-only">Letter detail</SheetTitle>
          <SheetDescription className="sr-only">
            Subject, body, and per-recipient read receipts for the selected
            letter.
          </SheetDescription>
          {selectedId !== null && (
            <LetterDetail key={selectedId} letterId={selectedId} />
          )}
        </SheetContent>
      </Sheet>

      <LetterComposeDialog
        open={composeOpen}
        onOpenChange={setComposeOpen}
        onCreated={(id) => setSelectedId(id)}
      />
    </>
  )
}
