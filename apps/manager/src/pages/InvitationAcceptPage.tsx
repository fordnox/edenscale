import { InvitationAcceptPage as SharedInvitationAcceptPage } from "@edenscale/ui/invitations/InvitationAcceptPage"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { orgPath } from "@/lib/managerRoutes"

const routes = {
  home: "/manager",
  login: "/manager/login",
  acceptPath: "/manager/invitations/accept",
  orgPath,
}

export default function InvitationAcceptPage() {
  const { setActiveOrganizationId } = useActiveOrganization()

  return (
    <SharedInvitationAcceptPage
      routes={routes}
      onOrganizationAccepted={setActiveOrganizationId}
    />
  )
}
