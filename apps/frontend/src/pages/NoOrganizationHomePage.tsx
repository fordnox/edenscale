import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { Landmark, Mail } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { config } from "@/lib/config"

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
            body="You haven't been invited to an organization yet. Check your email for a pending invitation, or create your own fund manager firm to get started."
            action={
              <Button
                variant="primary"
                size="md"
                onClick={() => navigate("/app/onboarding")}
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
