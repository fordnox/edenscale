import { useMemo } from "react"

import { usePendingInvitationsBanner } from "@/contexts/PendingInvitationsBannerContext"
import { useApiQuery } from "@/hooks/useApiQuery"
import { useAuth } from "@/hooks/useAuth"

export function usePendingInvitations() {
  const { isAuthenticated } = useAuth()
  const { bannerDismissed, dismissBanner, declinedIds } =
    usePendingInvitationsBanner()

  const pendingInvitationsQuery = useApiQuery(
    "/invitations/pending-for-me",
    undefined,
    { enabled: isAuthenticated, staleTime: 60 * 1000 },
  )

  const visibleInvitations = useMemo(
    () =>
      (pendingInvitationsQuery.data ?? []).filter(
        (inv) => !declinedIds.has(inv.id),
      ),
    [pendingInvitationsQuery.data, declinedIds],
  )

  const hasPendingInvitations = visibleInvitations.length > 0
  const showBanner = hasPendingInvitations && !bannerDismissed

  return { visibleInvitations, hasPendingInvitations, showBanner, dismissBanner }
}
