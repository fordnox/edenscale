import { InvitationAcceptPage as SharedInvitationAcceptPage } from "@edenscale/ui/invitations/InvitationAcceptPage"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { orgPath } from "@/lib/investorRoutes"

const routes = {
  home: "/investor",
  login: "/investor/login",
  acceptPath: "/investor/invitations/accept",
  orgPath,
}

export default function InvitationAcceptPage() {
  const { setActiveOrganizationId } = useInvestorOrganizations()

  return (
    <SharedInvitationAcceptPage
      routes={routes}
      onOrganizationAccepted={setActiveOrganizationId}
    />
  )
}
