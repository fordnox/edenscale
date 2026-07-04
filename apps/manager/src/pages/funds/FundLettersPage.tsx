import { Link, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useFundContext } from "@/layouts/FundLayout"
import { orgPath } from "@/lib/managerRoutes"
import { formatDate, titleCase } from "@edenscale/shared/format"

export default function FundLettersPage() {
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { fund } = useFundContext()

  const lettersQuery = useApiQuery("/funds/{fund_id}/communications", {
    params: { path: { fund_id: fund.id }, query: { limit: 5 } },
  })
  const letters = lettersQuery.data ?? []

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <Eyebrow>Letters ({letters.length})</Eyebrow>
      </div>
      <Card>
        <CardSection className="pt-4">
          {lettersQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : letters.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-4">
              <Eyebrow>No letters yet</Eyebrow>
              <p className="font-sans text-[14px] text-ink-700">
                Quarterly letters and other communications sent against this fund will be listed here.
              </p>
              <Link
                to={orgPath(orgSlug ?? "", "letters")}
                className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700"
              >
                Drafting space →
              </Link>
            </div>
          ) : (
            <ul className="divide-y divide-[color:var(--border-hairline)]">
              {letters.map((letter) => (
                <li
                  key={letter.id}
                  className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"
                >
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="font-sans text-[14px] font-medium text-ink-900">
                      {letter.subject}
                    </span>
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                      <span>{titleCase(letter.type)}</span>
                      {letter.sent_at && (
                        <>
                          <span className="size-1 rounded-full bg-ink-300" />
                          <span>Sent {formatDate(letter.sent_at)}</span>
                        </>
                      )}
                      {letter.recipients.length > 0 && (
                        <>
                          <span className="size-1 rounded-full bg-ink-300" />
                          <span>{letter.recipients.length} recipients</span>
                        </>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>
    </>
  )
}
