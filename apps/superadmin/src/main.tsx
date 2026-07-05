import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { HelmetProvider } from 'react-helmet-async'
import { Toaster } from 'sonner'
import App from './App'
import { configureApiClient } from '@edenscale/api/client'
import { queryClient } from '@edenscale/api/queryClient'
import { getSessionToken } from '@edenscale/auth/hanko'
import { AuthProvider } from '@edenscale/auth/useAuth'
import '@edenscale/ui/styles.css'

configureApiClient({
  unauthorizedOrganizationFallbackPath: '/superadmin',
  getSessionToken,
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <App />
            <Toaster position="bottom-right" richColors />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </HelmetProvider>
  </React.StrictMode>,
)
