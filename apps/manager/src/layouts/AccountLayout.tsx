import { Outlet } from "react-router-dom"

import { PendingInvitationsBanner } from "@edenscale/ui/invitations/PendingInvitationsBanner"
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
import { Topbar } from "@/components/layout/Topbar"

// Account view: the cross-organization state at /manager (and the reserved
// /manager/profile and /manager/notifications pages). Uses the shared Topbar
// without an active organization, so the org switcher stays one click away —
// nav tabs and search only appear once a workspace is open.
export default function AccountLayout() {
  const { visibleInvitations, showBanner, dismissBanner } =
    usePendingInvitations()

  return (
    <div className="flex min-h-svh flex-col es-paper text-ink-900">
      {showBanner && (
        <PendingInvitationsBanner
          invitations={visibleInvitations}
          onDismiss={dismissBanner}
          emphasize
        />
      )}
      <Topbar />
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
