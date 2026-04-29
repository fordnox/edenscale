import { Outlet } from "react-router-dom"
import { Sidebar } from "@/components/layout/Sidebar"

export default function AppShell() {
  return (
    <div className="flex min-h-svh bg-page text-ink-900">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
