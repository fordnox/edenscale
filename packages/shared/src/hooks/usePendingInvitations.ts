import { useContext, useMemo } from "react"

import { OrgSelectionContext } from "@edenscale/shared/contexts/OrgSelectionContext"
import { usePendingInvitationsBanner } from "@edenscale/shared/contexts/PendingInvitationsBannerContext"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useAuth } from "@edenscale/auth/useAuth"

export function usePendingInvitations() {
  const { isAuthenticated } = useAuth()
  const { bannerDismissed, dismissBanner, declinedIds } =
    usePendingInvitationsBanner()
  // Invitations follow the app's role scope: an LP invitation is the investor
  // app's business, a manager invitation the manager app's — the invitation
  // email already deep-links into the matching SPA (see _build_accept_url on
  // the backend), so out-of-scope invitations are simply not surfaced here.
  const appRoles = useContext(OrgSelectionContext)?.appRoles ?? null

  const pendingInvitationsQuery = useApiQuery(
    "/invitations/pending-for-me",
    undefined,
    { enabled: isAuthenticated, staleTime: 60 * 1000 },
  )

  const visibleInvitations = useMemo(
    () =>
      (pendingInvitationsQuery.data ?? []).filter(
        (inv) =>
          !declinedIds.has(inv.id) &&
          (!appRoles || appRoles.includes(inv.role)),
      ),
    [pendingInvitationsQuery.data, declinedIds, appRoles],
  )

  const hasPendingInvitations = visibleInvitations.length > 0
  const showBanner = hasPendingInvitations && !bannerDismissed

  return { visibleInvitations, hasPendingInvitations, showBanner, dismissBanner }
}
