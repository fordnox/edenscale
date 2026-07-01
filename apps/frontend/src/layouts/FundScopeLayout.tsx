import { Loader2 } from "lucide-react"
import { useParams } from "react-router-dom"

import { PageHero } from "@/components/layout/PageHero"
import FundDetailPage from "@/pages/FundDetailPage"
import { useApiQuery } from "@/hooks/useApiQuery"

export default function FundScopeLayout() {
  const { fundSlug } = useParams<{ fundSlug: string }>()
  const fundsQuery = useApiQuery("/funds")

  if (fundsQuery.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  const fund = fundsQuery.data?.find((f) => f.slug === fundSlug)

  if (!fund) {
    return (
      <PageHero
        eyebrow="Programmes"
        title="Fund not found."
        description="We were unable to load this fund. It may have been archived or the link is incorrect."
      />
    )
  }

  return <FundDetailPage fundId={fund.id} />
}
