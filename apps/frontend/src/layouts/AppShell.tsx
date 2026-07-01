import { useState } from "react"
import { Outlet } from "react-router-dom"

import { CommandPalette } from "@/components/layout/CommandPalette"
import { Sidebar } from "@/components/layout/Sidebar"
import { Topbar } from "@/components/layout/Topbar"
import { PendingInvitationsBanner } from "@/components/invitations/PendingInvitationsBanner"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useCommandPalette } from "@/hooks/useCommandPalette"
import { usePendingInvitations } from "@/hooks/usePendingInvitations"

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const { memberships } = useActiveOrganization()
  const { visibleInvitations, showBanner, dismissBanner } =
    usePendingInvitations()

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
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}
