import { Routes, Route } from 'react-router-dom'
import { ActiveOrganizationProvider } from './contexts/ActiveOrganizationContext'
import AppShell from './layouts/AppShell'
import DashboardPage from './pages/DashboardPage'
import FundsPage from './pages/FundsPage'
import FundDetailPage from './pages/FundDetailPage'
import InvestorsPage from './pages/InvestorsPage'
import CapitalCallsPage from './pages/CapitalCallsPage'
import DistributionsPage from './pages/DistributionsPage'
import DocumentsPage from './pages/DocumentsPage'
import LettersPage from './pages/LettersPage'
import TasksPage from './pages/TasksPage'
import NotificationsPage from './pages/NotificationsPage'
import ProfilePage from './pages/ProfilePage'
import OrganizationSettingsPage from './pages/OrganizationSettingsPage'
import AuditLogPage from './pages/AuditLogPage'
import LoginPage from './pages/LoginPage'

function App() {
  return (
    <ActiveOrganizationProvider>
      <Routes>
        {/* Dashboard application shell (sidebar + main) */}
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/funds" element={<FundsPage />} />
          <Route path="/funds/:fundId" element={<FundDetailPage />} />
          <Route path="/investors" element={<InvestorsPage />} />
          <Route path="/calls" element={<CapitalCallsPage />} />
          <Route path="/distributions" element={<DistributionsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/letters" element={<LettersPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route
            path="/settings/organization"
            element={<OrganizationSettingsPage />}
          />
          <Route path="/audit-log" element={<AuditLogPage />} />
        </Route>

        {/* Pages without layout */}
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </ActiveOrganizationProvider>
  )
}

export default App
