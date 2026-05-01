import { useState } from "react"
import { Outlet } from "react-router-dom"
import { Mail } from "lucide-react"

import { CommandPalette } from "@/components/layout/CommandPalette"
import { Sidebar } from "@/components/layout/Sidebar"
import { Topbar } from "@/components/layout/Topbar"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useCommandPalette } from "@/hooks/useCommandPalette"

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const { memberships, isSuperadmin, isLoading } = useActiveOrganization()

  const showNoOrgEmptyState =
    !isLoading && memberships.length === 0 && !isSuperadmin

  return (
    <div className="flex min-h-svh bg-page text-ink-900">
      <Sidebar
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        onOpenSearch={() => setPaletteOpen(true)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
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
