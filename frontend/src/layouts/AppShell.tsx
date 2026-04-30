import { useState } from "react"
import { Outlet } from "react-router-dom"
import { CommandPalette } from "@/components/layout/CommandPalette"
import { Sidebar } from "@/components/layout/Sidebar"
import { Topbar } from "@/components/layout/Topbar"
import { useCommandPalette } from "@/hooks/useCommandPalette"

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()

  return (
    <div className="flex min-h-svh bg-page text-ink-900">
      <Sidebar open={sidebarOpen} onOpenChange={setSidebarOpen} />
      <div className="flex min-w-0 flex-1 flex-col">
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
