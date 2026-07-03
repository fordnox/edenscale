import { Navigate, Routes, Route, Outlet } from 'react-router-dom'
import { ActiveOrganizationProvider } from '@edenscale/shared/contexts/ActiveOrganizationContext'
import { PendingInvitationsBannerProvider } from '@edenscale/shared/contexts/PendingInvitationsBannerContext'
import { useActiveOrganization } from './hooks/useActiveOrganization'
import ProtectedLayout from './layouts/ProtectedLayout'
import AccountLayout from './layouts/AccountLayout'
import OrgLayout from './layouts/OrgLayout'
import FundLayout from './layouts/FundLayout'
import UserDashboardPage from './pages/UserDashboardPage'
import NoOrganizationHomePage from './pages/NoOrganizationHomePage'
import DashboardPage from './pages/DashboardPage'
import FundsPage from './pages/FundsPage'
import CapitalCallsPage from './pages/CapitalCallsPage'
import DistributionsPage from './pages/DistributionsPage'
import DocumentsPage from './pages/DocumentsPage'
import ReportsPage from './pages/ReportsPage'
import ArchivePage from './pages/ArchivePage'
import LettersPage from './pages/LettersPage'
import NotificationsPage from './pages/NotificationsPage'
import ProfilePage from './pages/ProfilePage'
import InvitationAcceptPage from './pages/InvitationAcceptPage'
import LoginPage from './pages/LoginPage'

function ProtectedProviders() {
  return (
    <ActiveOrganizationProvider>
      <PendingInvitationsBannerProvider>
        <Outlet />
      </PendingInvitationsBannerProvider>
    </ActiveOrganizationProvider>
  )
}

// Bare /investor landing: pre-org-selection state for signed-in LPs. Shows the
// portfolio home (org picker + cross-org figures), or the "no organization yet"
// entry point when the user isn't a member of any org.
function AppRootRoute() {
  const { memberships, isLoading } = useActiveOrganization()
  if (isLoading) return null
  if (memberships.length === 0) return <NoOrganizationHomePage />
  return <UserDashboardPage />
}

function App() {
  return (
    <Routes>
      {/* Pages without authenticated app providers */}
      <Route path="/investor/login" element={<LoginPage />} />

      {/* Authenticated application routes */}
      <Route element={<ProtectedLayout />}>
        <Route element={<ProtectedProviders />}>
          <Route
            path="/investor/invitations/accept"
            element={<InvitationAcceptPage />}
          />

          {/* Reserved top-level /investor/* paths — static siblings of
              /investor/:orgSlug so they always win the route match. */}
          <Route element={<AccountLayout />}>
            <Route path="/investor" element={<AppRootRoute />} />
            <Route path="/investor/profile" element={<ProfilePage />} />
          </Route>

          {/* Organization workspace */}
          <Route path="/investor/:orgSlug" element={<OrgLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="funds" element={<FundsPage />} />
            <Route path="calls" element={<CapitalCallsPage />} />
            <Route path="distributions" element={<DistributionsPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="archive" element={<ArchivePage />} />
            <Route path="letters" element={<LettersPage />} />
            <Route path="notifications" element={<NotificationsPage />} />

            {/* Fund workspace */}
            <Route path=":fundSlug" element={<FundLayout />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/investor" replace />} />
    </Routes>
  )
}

export default App
