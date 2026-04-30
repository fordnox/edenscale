import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import AppShell from './layouts/AppShell'
import DashboardPage from './pages/DashboardPage'
import { ComingSoon } from './pages/ComingSoon'
import FundsPage from './pages/FundsPage'
import UserProfilePage from './pages/UserProfilePage'
import LoginPage from './pages/LoginPage'

function App() {
  return (
    <Routes>
      {/* Dashboard application shell (sidebar + main) */}
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/funds" element={<FundsPage />} />
        <Route path="/investors" element={<ComingSoon page="Investors" />} />
        <Route path="/calls" element={<ComingSoon page="Capital Calls" />} />
        <Route path="/distributions" element={<ComingSoon page="Distributions" />} />
        <Route path="/documents" element={<ComingSoon page="Documents" />} />
        <Route path="/letters" element={<ComingSoon page="Letters" />} />
        <Route path="/tasks" element={<ComingSoon page="Tasks" />} />
        <Route path="/notifications" element={<ComingSoon page="Notifications" />} />
      </Route>

      {/* Marketing / profile pages with the legacy header + footer layout */}
      <Route element={<MainLayout />}>
        <Route path="/profile" element={<UserProfilePage />} />
      </Route>

      {/* Pages without layout */}
      <Route path="/login" element={<LoginPage />} />
    </Routes>
  )
}

export default App
