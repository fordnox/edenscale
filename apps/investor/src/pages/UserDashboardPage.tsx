import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"

import { BrandMark } from "@edenscale/brand/components/BrandMark"
import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Button } from "@edenscale/ui/button"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { orgPath } from "@/lib/investorRoutes"
import { config } from "@edenscale/api/config"

// Account root (/investor): the cross-organization landing for a signed-in LP.
// Lists the organizations whose investor materials they can view; most LPs
// belong to exactly one and go straight in from here.
export default function UserDashboardPage() {
  const { organizations } = useInvestorOrganizations()

  return (
    <>
      <Helmet>
        <title>{`Your portfolio · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Investor portal"
        title="Your portfolio."
        description="The firms you invest with. Open a workspace to review your commitments, capital activity, documents, and letters."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Eyebrow>Your organizations</Eyebrow>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {organizations.map((entry) => (
            <Card key={entry.organization_id}>
              <CardSection>
                <div className="flex items-start gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
                    <BrandMark className="size-5" />
                  </span>
                  <div className="flex min-w-0 flex-col">
                    <h3 className="truncate font-display text-[20px] leading-tight tracking-tight text-ink-900">
                      {entry.organization.name}
                    </h3>
                    <span className="font-sans text-[12px] text-ink-500">
                      Investor
                    </span>
                  </div>
                </div>
                <div className="mt-5 border-t border-[color:var(--border-hairline)] pt-4">
                  <Button asChild variant="secondary" size="sm" className="w-full">
                    <Link to={orgPath(entry.organization.slug)}>
                      Open workspace
                    </Link>
                  </Button>
                </div>
              </CardSection>
            </Card>
          ))}
        </div>
      </div>
    </>
  )
}
