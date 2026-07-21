import { lazy, Suspense } from 'react'
import { Navigate, Routes, Route, Outlet } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { ActiveOrganizationProvider } from '@edenscale/shared/contexts/ActiveOrganizationContext'
import { PendingInvitationsBannerProvider } from '@edenscale/shared/contexts/PendingInvitationsBannerContext'
import { useActiveOrganization } from './hooks/useActiveOrganization'
import { ProtectedLayout } from '@edenscale/ui/ProtectedLayout'
import AccountLayout from './layouts/AccountLayout'
import OrgLayout from './layouts/OrgLayout'
import FundLayout from './layouts/FundLayout'
import { RequireRole } from './components/RequireRole'

// Route-level code splitting: every page below is loaded on demand so that,
// e.g., the login screen doesn't pull in recharts (via FundOverviewPage) or
// the bank-import wizard. Layouts stay eager — they're shell chrome needed
// immediately once a route matches.
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const UserDashboardPage = lazy(() => import('./pages/UserDashboardPage'))
const NoOrganizationHomePage = lazy(() => import('./pages/NoOrganizationHomePage'))
const FundsPage = lazy(() => import('./pages/FundsPage'))
const InvestorsPage = lazy(() => import('./pages/InvestorsPage'))
const CapitalCallsPage = lazy(() => import('./pages/CapitalCallsPage'))
const ImportBankPaymentsPage = lazy(() => import('./pages/ImportBankPaymentsPage'))
const DistributionsPage = lazy(() => import('./pages/DistributionsPage'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'))
const LettersPage = lazy(() => import('./pages/LettersPage'))
const TasksPage = lazy(() => import('./pages/TasksPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const OrganizationSettingsPage = lazy(() => import('./pages/OrganizationSettingsPage'))
const AuditLogPage = lazy(() => import('./pages/AuditLogPage'))
const InvitationAcceptPage = lazy(() => import('./pages/InvitationAcceptPage'))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'))
const FundOverviewPage = lazy(() => import('./pages/funds/FundOverviewPage'))
const FundCommitmentsPage = lazy(() => import('./pages/funds/FundCommitmentsPage'))
const FundCapitalCallsPage = lazy(() => import('./pages/funds/FundCapitalCallsPage'))
const FundDistributionsPage = lazy(() => import('./pages/funds/FundDistributionsPage'))
const FundDocumentsPage = lazy(() => import('./pages/funds/FundDocumentsPage'))
const FundLettersPage = lazy(() => import('./pages/funds/FundLettersPage'))
const FundSettingsPage = lazy(() => import('./pages/funds/FundSettingsPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))

// Matches the loading state already used by ProtectedLayout/OrgLayout while
// org/auth data resolves, so a lazy route swap doesn't look different from
// the loading states users already see.
function RouteLoadingFallback() {
  return (
    <main className="flex-1 container mx-auto px-6 py-8">
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    </main>
  )
}

// The manager app serves only the manager slice of an account. The same login
// may also be an LP elsewhere, but those memberships and invitations are
// invisible here — the investor app is a fully separate SPA with its own scope.
const MANAGER_ROLES = ['admin', 'fund_manager'] as const

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
  const { memberships, isLoading } = useActiveOrganization()
  if (isLoading) return null

  const hasOrgAccess = memberships.length > 0
  if (!hasOrgAccess) return <NoOrganizationHomePage />

  return <UserDashboardPage />
}

function App() {
  return (
    <Suspense fallback={<RouteLoadingFallback />}>
      <Routes>
        {/* Pages without authenticated app providers */}
        <Route path="/manager/login" element={<LoginPage />} />

        {/* Authenticated application routes */}
        <Route element={<ProtectedLayout loginPath="/manager/login" />}>
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
              <Route path="/manager/notifications" element={<NotificationsPage />} />
            </Route>

            {/* Organization workspace */}
            <Route path="/manager/:orgSlug" element={<OrgLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="funds" element={<FundsPage />} />
              <Route path="investors" element={<InvestorsPage />} />
              <Route path="calls" element={<CapitalCallsPage />} />
              <Route
                path="calls/import"
                element={
                  <RequireRole allowed={MANAGER_ROLES}>
                    <ImportBankPaymentsPage />
                  </RequireRole>
                }
              />
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
              {/* Notifications are user-scoped and moved to /manager/notifications;
                  keep the old org path redirecting so bookmarks survive and the
                  segment never falls through to the :fundSlug route. */}
              <Route
                path="notifications"
                element={<Navigate to="/manager/notifications" replace />}
              />
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
                <Route path="documents" element={<FundDocumentsPage />} />
                <Route path="letters" element={<FundLettersPage />} />
                <Route path="settings" element={<FundSettingsPage />} />
              </Route>
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/manager" replace />} />
      </Routes>
    </Suspense>
  )
}

export default App
