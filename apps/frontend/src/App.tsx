import { Routes, Route, Outlet } from 'react-router-dom'
import { ActiveOrganizationProvider } from './contexts/ActiveOrganizationContext'
import { PendingInvitationsBannerProvider } from './contexts/PendingInvitationsBannerContext'
import { useActiveOrganization } from './hooks/useActiveOrganization'
import DashboardShell from './layouts/DashboardShell'
import ProtectedLayout from './layouts/ProtectedLayout'
import RequireOrganization from './layouts/RequireOrganization'
import DashboardPage from './pages/DashboardPage'
import NoOrganizationHomePage from './pages/NoOrganizationHomePage'
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
import SuperadminOrganizationsPage from './pages/superadmin/SuperadminOrganizationsPage'
import SuperadminOrganizationDetailPage from './pages/superadmin/SuperadminOrganizationDetailPage'
import InvitationAcceptPage from './pages/InvitationAcceptPage'
import OnboardingPage from './pages/OnboardingPage'
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

function HomeRoute() {
  const { memberships, isSuperadmin, isLoading } = useActiveOrganization()
  if (isLoading) return null
  const hasOrgAccess = memberships.length > 0 || isSuperadmin
  return hasOrgAccess ? <DashboardPage /> : <NoOrganizationHomePage />
}

function App() {
  return (
    <Routes>
      {/* Pages without authenticated app providers */}
      <Route path="/login" element={<LoginPage />} />

      {/* Authenticated application routes */}
      <Route element={<ProtectedLayout />}>
        <Route element={<ProtectedProviders />}>
          <Route
            path="/invitations/accept"
            element={<InvitationAcceptPage />}
          />
          <Route path="/onboarding" element={<OnboardingPage />} />

          {/* Dashboard application shell (full app shell, or a minimal
              shell for users without an organization) */}
          <Route element={<DashboardShell />}>
            <Route path="/" element={<HomeRoute />} />
            <Route path="/profile" element={<ProfilePage />} />

            {/* Everything below requires an active organization */}
            <Route element={<RequireOrganization />}>
              <Route path="/funds" element={<FundsPage />} />
              <Route path="/funds/:fundId" element={<FundDetailPage />} />
              <Route path="/investors" element={<InvestorsPage />} />
              <Route path="/calls" element={<CapitalCallsPage />} />
              <Route path="/distributions" element={<DistributionsPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/letters" element={<LettersPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route
                path="/settings/organization"
                element={<OrganizationSettingsPage />}
              />
              <Route path="/audit-log" element={<AuditLogPage />} />
              <Route
                path="/superadmin/organizations"
                element={<SuperadminOrganizationsPage />}
              />
              <Route
                path="/superadmin/organizations/:organizationId"
                element={<SuperadminOrganizationDetailPage />}
              />
            </Route>
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}

export default App
