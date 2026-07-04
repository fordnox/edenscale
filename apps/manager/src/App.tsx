import { Navigate, Routes, Route, Outlet } from 'react-router-dom'
import { ActiveOrganizationProvider } from '@edenscale/shared/contexts/ActiveOrganizationContext'
import { PendingInvitationsBannerProvider } from '@edenscale/shared/contexts/PendingInvitationsBannerContext'
import { useActiveOrganization } from './hooks/useActiveOrganization'
import ProtectedLayout from './layouts/ProtectedLayout'
import AccountLayout from './layouts/AccountLayout'
import OrgLayout from './layouts/OrgLayout'
import FundLayout from './layouts/FundLayout'
import DashboardPage from './pages/DashboardPage'
import UserDashboardPage from './pages/UserDashboardPage'
import NoOrganizationHomePage from './pages/NoOrganizationHomePage'
import FundsPage from './pages/FundsPage'
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
import FundOverviewPage from './pages/funds/FundOverviewPage'
import FundCommitmentsPage from './pages/funds/FundCommitmentsPage'
import FundCapitalCallsPage from './pages/funds/FundCapitalCallsPage'
import FundDistributionsPage from './pages/funds/FundDistributionsPage'
import FundTeamPage from './pages/funds/FundTeamPage'
import FundLettersPage from './pages/funds/FundLettersPage'
import LoginPage from './pages/LoginPage'
import { RequireRole } from './components/RequireRole'

// The manager app serves only the manager slice of an account. The same login
// may also be an LP elsewhere, but those memberships and invitations are
// invisible here — the investor app is a fully separate SPA with its own scope.
const MANAGER_ROLES = ['admin', 'fund_manager', 'superadmin'] as const

function ProtectedProviders() {
  return (
    <ActiveOrganizationProvider roles={MANAGER_ROLES}>
      <PendingInvitationsBannerProvider>
        <Outlet />
      </PendingInvitationsBannerProvider>
    </ActiveOrganizationProvider>
  )
}

// Bare /manager landing: pre-org-selection state for signed-in users. Redirects
// straight into an org's workspace once one is resolvable; otherwise shows
// the "no organization yet" onboarding entry point.
function AppRootRoute() {
  const { memberships, isSuperadmin, isLoading } = useActiveOrganization()
  if (isLoading) return null

  const hasOrgAccess = memberships.length > 0 || isSuperadmin
  if (!hasOrgAccess) return <NoOrganizationHomePage />

  return <UserDashboardPage />
}

function App() {
  return (
    <Routes>
      {/* Pages without authenticated app providers */}
      <Route path="/manager/login" element={<LoginPage />} />

      {/* Authenticated application routes */}
      <Route element={<ProtectedLayout />}>
        <Route element={<ProtectedProviders />}>
          <Route
            path="/manager/invitations/accept"
            element={<InvitationAcceptPage />}
          />
          <Route path="/manager/onboarding" element={<OnboardingPage />} />

          {/* Reserved top-level /manager/* paths — declared as static siblings
              of /manager/:orgSlug below so they always win the route match
              regardless of an org happening to share the segment name. */}
          <Route element={<AccountLayout />}>
            <Route path="/manager" element={<AppRootRoute />} />
            <Route path="/manager/profile" element={<ProfilePage />} />
            <Route
              path="/manager/superadmin/organizations"
              element={<SuperadminOrganizationsPage />}
            />
            <Route
              path="/manager/superadmin/organizations/:organizationId"
              element={<SuperadminOrganizationDetailPage />}
            />
          </Route>

          {/* Organization workspace */}
          <Route path="/manager/:orgSlug" element={<OrgLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="funds" element={<FundsPage />} />
            <Route path="investors" element={<InvestorsPage />} />
            <Route path="calls" element={<CapitalCallsPage />} />
            <Route path="distributions" element={<DistributionsPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="letters" element={<LettersPage />} />
            <Route
              path="tasks"
              element={
                <RequireRole allowed={MANAGER_ROLES}>
                  <TasksPage />
                </RequireRole>
              }
            />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="settings" element={<OrganizationSettingsPage />} />
            <Route
              path="audit-log"
              element={
                <RequireRole allowed={MANAGER_ROLES}>
                  <AuditLogPage />
                </RequireRole>
              }
            />

            {/* Fund workspace — each section is its own page under the
                shared fund chrome (hero + KPI strip) in FundLayout. */}
            <Route path=":fundSlug" element={<FundLayout />}>
              <Route index element={<FundOverviewPage />} />
              <Route path="commitments" element={<FundCommitmentsPage />} />
              <Route path="calls" element={<FundCapitalCallsPage />} />
              <Route path="distributions" element={<FundDistributionsPage />} />
              <Route path="team" element={<FundTeamPage />} />
              <Route path="letters" element={<FundLettersPage />} />
            </Route>
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/manager" replace />} />
    </Routes>
  )
}

export default App
