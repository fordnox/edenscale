import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { Landmark, Mail } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { config } from "@edenscale/api/config"

export default function NoOrganizationHomePage() {
  const navigate = useNavigate()

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
            body="You haven't been invited to an organization yet. Check your email for a pending invitation, create your own fund manager firm, or explore the demo firm to get started."
            action={
              <Button
                variant="primary"
                size="md"
                onClick={() => navigate("/manager/onboarding")}
              >
                <Landmark strokeWidth={1.5} className="size-4" />
                Create your firm
              </Button>
            }
          />
        </Card>
      </div>
    </>
  )
}
