import { useMemo, useState } from "react"
import { Outlet } from "react-router-dom"
import { Mail } from "lucide-react"

import { CommandPalette } from "@/components/layout/CommandPalette"
import { Sidebar } from "@/components/layout/Sidebar"
import { Topbar } from "@/components/layout/Topbar"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { PendingInvitationsBanner } from "@/components/invitations/PendingInvitationsBanner"
import { usePendingInvitationsBanner } from "@/contexts/PendingInvitationsBannerContext"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@/hooks/useApiQuery"
import { useAuth } from "@/hooks/useAuth"
import { useCommandPalette } from "@/hooks/useCommandPalette"

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const { memberships, isSuperadmin, isLoading } = useActiveOrganization()
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

  const showNoOrgEmptyState =
    !isLoading &&
    memberships.length === 0 &&
    !isSuperadmin &&
    !hasPendingInvitations

  return (
    <div className="flex min-h-svh bg-page text-ink-900">
      <Sidebar
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        onOpenSearch={() => setPaletteOpen(true)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        {showBanner && (
          <PendingInvitationsBanner
            invitations={visibleInvitations}
            onDismiss={dismissBanner}
            emphasize={memberships.length === 0}
          />
        )}
        <Topbar
          onOpenSidebar={() => setSidebarOpen(true)}
          onOpenSearch={() => setPaletteOpen(true)}
        />
        <main className="flex flex-1 flex-col">
          {showNoOrgEmptyState ? (
            <div className="flex flex-1 items-center justify-center px-4 py-16 md:px-8">
              <Card className="w-full max-w-xl">
                <EmptyState
                  icon={<Mail strokeWidth={1.25} />}
                  title="No organization yet"
                  body="You haven't been invited to an organization yet. Check your email for a pending invitation, or contact your administrator."
                />
              </Card>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}
