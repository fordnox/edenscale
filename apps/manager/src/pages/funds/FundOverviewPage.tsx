import { Loader2 } from "lucide-react"

import { FundOverview } from "@/components/funds/FundOverview"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useFundContext } from "@/layouts/FundLayout"

export default function FundOverviewPage() {
  const { fund, canManage } = useFundContext()

  const overviewQuery = useApiQuery("/funds/{fund_id}/overview", {
    params: { path: { fund_id: fund.id } },
  })
  const commitmentsQuery = useApiQuery("/funds/{fund_id}/commitments", {
    params: { path: { fund_id: fund.id } },
  })
  const callsQuery = useApiQuery("/funds/{fund_id}/capital-calls", {
    params: { path: { fund_id: fund.id } },
  })
  const distributionsQuery = useApiQuery("/funds/{fund_id}/distributions", {
    params: { path: { fund_id: fund.id } },
  })

  if (
    callsQuery.isLoading ||
    distributionsQuery.isLoading ||
    commitmentsQuery.isLoading
  ) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
      </div>
    )
  }

  return (
    <FundOverview
      fund={fund}
      overview={overviewQuery.data}
      calls={callsQuery.data ?? []}
      distributions={distributionsQuery.data ?? []}
      commitments={commitmentsQuery.data ?? []}
      canManage={canManage}
    />
  )
}
