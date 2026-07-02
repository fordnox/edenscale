import { Loader2 } from "lucide-react"
import { useParams } from "react-router-dom"

import { PageHero } from "@edenscale/ui/PageHero"
import { InvestorFundDetailPage } from "@/pages/InvestorReadOnlyPages"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"

export default function FundScopeLayout() {
  const { fundSlug } = useParams<{ fundSlug: string }>()
  // Resolve the fund directly by slug (O(1) on the backend) rather than
  // scanning the paginated /funds list, which would miss funds past the
  // default page size.
  const fundQuery = useApiQuery(
    "/funds/by-slug/{slug}",
    { params: { path: { slug: fundSlug ?? "" } } },
    { enabled: Boolean(fundSlug), retry: false },
  )

  if (fundQuery.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  const fund = fundQuery.data

  if (!fund) {
    return (
      <PageHero
        eyebrow="Programmes"
        title="Fund not found."
        description="We were unable to load this fund. It may have been archived or the link is incorrect."
      />
    )
  }

  return <InvestorFundDetailPage fundId={fund.id} />
}
