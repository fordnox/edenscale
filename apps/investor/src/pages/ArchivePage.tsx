import { Helmet } from "react-helmet-async"

import { PageHero } from "@edenscale/ui/PageHero"
import { UpdatesFeed } from "@/components/UpdatesFeed"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { config } from "@edenscale/api/config"

// The full activity history — every capital notice, distribution, and letter,
// newest first. The dashboard feed is the recent slice of this.
export default function ArchivePage() {
  const { activeOrganization } = useInvestorOrganizations()
  const orgSlug = activeOrganization?.organization.slug ?? null

  return (
    <>
      <Helmet>
        <title>{`Archive · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Archive"
        title="Everything, in order."
        description="The complete history of capital notices, distributions, and correspondence for your account."
      />
      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <UpdatesFeed orgSlug={orgSlug} limit={500} />
      </div>
    </>
  )
}
