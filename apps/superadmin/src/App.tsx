import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedLayout from './layouts/ProtectedLayout'
import SuperadminLayout from './layouts/SuperadminLayout'
import LoginPage from './pages/LoginPage'
import OrganizationsPage from './pages/OrganizationsPage'
import OrganizationDetailPage from './pages/OrganizationDetailPage'

// The superadmin SPA is the platform control surface, mounted at /superadmin
// by the gateway. Every page is gated on the global superadmin role inside
// SuperadminLayout; there is no organization context here — /superadmin/* API
// routes intentionally do not use the X-Organization-Id header.
function App() {
  return (
    <Routes>
      <Route path="/superadmin/login" element={<LoginPage />} />

      <Route element={<ProtectedLayout />}>
        <Route element={<SuperadminLayout />}>
          <Route path="/superadmin" element={<OrganizationsPage />} />
          <Route
            path="/superadmin/organizations/:organizationId"
            element={<OrganizationDetailPage />}
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/superadmin" replace />} />
    </Routes>
  )
}

export default App
