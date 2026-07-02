import { Navigate, Routes, Route, Outlet } from 'react-router-dom'
import { ActiveOrganizationProvider } from '@edenscale/shared/contexts/ActiveOrganizationContext'
import { PendingInvitationsBannerProvider } from '@edenscale/shared/contexts/PendingInvitationsBannerContext'
import { useActiveOrganization } from './hooks/useActiveOrganization'
import DashboardShell from './layouts/DashboardShell'
import ProtectedLayout from './layouts/ProtectedLayout'
import OrgScopeLayout from './layouts/OrgScopeLayout'
import FundScopeLayout from './layouts/FundScopeLayout'
import NoOrganizationHomePage from './pages/NoOrganizationHomePage'
import ProfilePage from './pages/ProfilePage'
import InvitationAcceptPage from './pages/InvitationAcceptPage'
import LoginPage from './pages/LoginPage'
import {
  InvestorCapitalCallsPage,
  InvestorDistributionsPage,
  InvestorDocumentsPage,
  InvestorFundDetailPage,
  InvestorFundsPage,
  InvestorHomePage,
  InvestorLettersPage,
  InvestorNotificationsPage,
  InvestorOverviewPage,
} from './pages/InvestorReadOnlyPages'

function ProtectedProviders() {
  return (
    <ActiveOrganizationProvider>
      <PendingInvitationsBannerProvider>
        <Outlet />
      </PendingInvitationsBannerProvider>
    </ActiveOrganizationProvider>
  )
}

// Bare /investor landing: pre-org-selection state for signed-in users. Redirects
// straight into an org's workspace once one is resolvable; otherwise shows
// the "no organization yet" onboarding entry point.
function AppRootRoute() {
  const { memberships, isLoading } = useActiveOrganization()
  if (isLoading) return null

  if (memberships.length === 0) return <NoOrganizationHomePage />

  return <InvestorHomePage />
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

          {/* Reserved top-level /investor/* paths — declared as static siblings
              of /investor/:orgSlug below so they always win the route match
              regardless of an org happening to share the segment name. */}
          <Route element={<DashboardShell />}>
            <Route path="/investor" element={<AppRootRoute />} />
            <Route path="/investor/profile" element={<ProfilePage />} />
          </Route>

          {/* Organization workspace */}
          <Route path="/investor/:orgSlug" element={<OrgScopeLayout />}>
            <Route index element={<InvestorOverviewPage />} />
            <Route path="funds" element={<InvestorFundsPage />} />
            <Route path="calls" element={<InvestorCapitalCallsPage />} />
            <Route path="distributions" element={<InvestorDistributionsPage />} />
            <Route path="documents" element={<InvestorDocumentsPage />} />
            <Route path="letters" element={<InvestorLettersPage />} />
            <Route path="notifications" element={<InvestorNotificationsPage />} />

            {/* Fund workspace */}
            <Route path=":fundSlug" element={<FundScopeLayout />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/investor" replace />} />
    </Routes>
  )
}

export default App
