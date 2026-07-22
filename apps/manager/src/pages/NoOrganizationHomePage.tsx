import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { Mail } from "lucide-react"

import { BrandMark } from "@edenscale/brand/components/BrandMark"
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
            body="You haven't been invited to an organization yet. Check your email for a pending invitation, create your own fund manager organization, or explore the demo organization to get started."
            action={
              <Button
                variant="primary"
                size="md"
                onClick={() => navigate("/manager/onboarding")}
              >
                <BrandMark className="size-4" />
                Create your organization
              </Button>
            }
          />
        </Card>
      </div>
    </>
  )
}
