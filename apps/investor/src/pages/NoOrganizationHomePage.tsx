import { Helmet } from "react-helmet-async"
import { Landmark, Mail } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { config } from "@edenscale/api/config"

export default function NoOrganizationHomePage() {
  return (
    <>
      <Helmet>
        <title>{`Get started · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <div className="flex flex-1 items-center justify-center px-4 py-16 md:px-8">
        <Card className="w-full max-w-xl">
          <EmptyState
            icon={<Mail strokeWidth={1.25} />}
            title="No organization yet"
            body="You haven't been invited to an organization yet. Check your email for a pending invitation, or create your own fund manager firm to get started."
            action={
              // Firm creation lives in the manager SPA — a hard navigation
              // is required to cross the /investor → /manager mount.
              <Button asChild variant="primary" size="md">
                <a href="/manager/onboarding">
                  <Landmark strokeWidth={1.5} className="size-4" />
                  Create your firm
                </a>
              </Button>
            }
          />
        </Card>
      </div>
    </>
  )
}
