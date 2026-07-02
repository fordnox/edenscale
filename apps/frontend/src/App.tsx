import { Navigate, Routes, Route, Outlet } from 'react-router-dom'
import { ActiveOrganizationProvider } from './contexts/ActiveOrganizationContext'
import { PendingInvitationsBannerProvider } from './contexts/PendingInvitationsBannerContext'
import { useActiveOrganization } from './hooks/useActiveOrganization'
import DashboardShell from './layouts/DashboardShell'
import ProtectedLayout from './layouts/ProtectedLayout'
import OrgScopeLayout from './layouts/OrgScopeLayout'
import FundScopeLayout from './layouts/FundScopeLayout'
import DashboardPage from './pages/DashboardPage'
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
import LoginPage from './pages/LoginPage'
import { RequireRole } from './components/RequireRole'
import { orgPath } from './lib/appRoutes'
import { getLastVisitedOrgSlug } from './lib/activeOrg'

const MANAGER_ROLES = ['admin', 'fund_manager', 'superadmin'] as const

function ProtectedProviders() {
  return (
    <ActiveOrganizationProvider>
      <PendingInvitationsBannerProvider>
        <Outlet />
      </PendingInvitationsBannerProvider>
    </ActiveOrganizationProvider>
  )
}

// Bare /app landing: pre-org-selection state for signed-in users. Redirects
// straight into an org's workspace once one is resolvable; otherwise shows
// the "no organization yet" onboarding entry point.
function AppRootRoute() {
  const { memberships, isSuperadmin, isLoading } = useActiveOrganization()
  if (isLoading) return null

  const hasOrgAccess = memberships.length > 0 || isSuperadmin
  if (!hasOrgAccess) return <NoOrganizationHomePage />

  const lastSlug = getLastVisitedOrgSlug()
  const target =
    memberships.find((m) => m.organization.slug === lastSlug) ?? memberships[0]
  if (!target) {
    // Pure superadmin with zero tenant memberships — nothing to land on.
    return <Navigate to="/app/superadmin/organizations" replace />
  }
  return <Navigate to={orgPath(target.organization.slug)} replace />
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
          <Route path="/app/onboarding" element={<OnboardingPage />} />

          {/* Reserved top-level /app/* paths — declared as static siblings
              of /app/:orgSlug below so they always win the route match
              regardless of an org happening to share the segment name. */}
          <Route element={<DashboardShell />}>
            <Route path="/app" element={<AppRootRoute />} />
            <Route path="/app/profile" element={<ProfilePage />} />
            <Route
              path="/app/superadmin/organizations"
              element={<SuperadminOrganizationsPage />}
            />
            <Route
              path="/app/superadmin/organizations/:organizationId"
              element={<SuperadminOrganizationDetailPage />}
            />
          </Route>

          {/* Organization workspace */}
          <Route path="/app/:orgSlug" element={<OrgScopeLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="funds" element={<FundsPage />} />
            {/* LPs may open this page too — the backend scopes the register
                to investors they are a linked contact for. */}
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

            {/* Fund workspace */}
            <Route path=":fundSlug" element={<FundScopeLayout />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  )
}

export default App
