import { useState } from "react"
import { Sidebar } from "@/components/layout/Sidebar"
import type { Route } from "@/lib/router"
import { DashboardPage } from "@/pages/DashboardPage"
import { FundsPage } from "@/pages/FundsPage"
import { FundDetailPage } from "@/pages/FundDetailPage"
import { InvestorsPage } from "@/pages/InvestorsPage"
import { CapitalCallsPage } from "@/pages/CapitalCallsPage"
import { DistributionsPage } from "@/pages/DistributionsPage"
import { DocumentsPage } from "@/pages/DocumentsPage"
import { LettersPage } from "@/pages/LettersPage"
import { TasksPage } from "@/pages/TasksPage"
import { NotificationsPage } from "@/pages/NotificationsPage"

export function App() {
  const [route, setRoute] = useState<Route>("dashboard")
  const [selectedFundId, setSelectedFundId] = useState<number | null>(null)

  function navigate(next: Route) {
    if (next !== "fund-detail") {
      setSelectedFundId(null)
    }
    setRoute(next)
    window.scrollTo({ top: 0, behavior: "instant" })
  }

  function selectFund(id: number) {
    setSelectedFundId(id)
    setRoute("fund-detail")
    window.scrollTo({ top: 0, behavior: "instant" })
  }

  return (
    <div className="flex min-h-svh bg-page text-ink-900">
      <Sidebar
        current={route === "fund-detail" ? "funds" : route}
        onNavigate={navigate}
      />
      <main className="flex min-w-0 flex-1 flex-col">
        {route === "dashboard" && <DashboardPage onNavigate={navigate} />}
        {route === "funds" && <FundsPage onSelect={selectFund} />}
        {route === "fund-detail" && selectedFundId !== null && (
          <FundDetailPage
            fundId={selectedFundId}
            onBack={() => navigate("funds")}
          />
        )}
        {route === "investors" && <InvestorsPage />}
        {route === "calls" && <CapitalCallsPage />}
        {route === "distributions" && <DistributionsPage />}
        {route === "documents" && <DocumentsPage />}
        {route === "letters" && <LettersPage />}
        {route === "tasks" && <TasksPage />}
        {route === "notifications" && <NotificationsPage />}
      </main>
    </div>
  )
}

export default App
