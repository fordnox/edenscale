import { Loader2 } from "lucide-react"
import { useParams } from "react-router-dom"

import { PageHero } from "@edenscale/ui/PageHero"
import FundDetailPage from "@/pages/FundDetailPage"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"

// Fund view: resolves the :fundSlug param to a fund and renders its LP detail
// page. Rendered inside OrgLayout's shell, so an org is already active.
export default function FundLayout() {
  const { fundSlug } = useParams<{ fundSlug: string }>()
  // Resolve the fund directly by slug (O(1) on the backend) rather than
  // scanning the paginated /funds list, which would miss funds past the
  // default page size.
  const fundQuery = useApiQuery(
    "/investor/funds/by-slug/{slug}",
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

  return <FundDetailPage fundId={fund.id} fundSlug={fundSlug ?? ""} />
}
