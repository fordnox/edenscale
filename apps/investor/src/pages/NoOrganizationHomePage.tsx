import { Helmet } from "react-helmet-async"
import { Mail } from "lucide-react"

import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { config } from "@edenscale/api/config"

// Shown to a signed-in user with no LP membership. This is the investor
// portal — access comes by invitation from a fund manager, so there is no
// firm-creation path here (that lives entirely in the manager app).
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
            title="No investments yet"
            body="You haven't been added to a fund yet. When your fund manager invites you, check your email for the invitation — accepting it will connect your account to your investments here."
          />
        </Card>
      </div>
    </>
  )
}
