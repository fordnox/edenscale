import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, useNavigate, Link } from 'react-router-dom'
import { QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { HelmetProvider } from 'react-helmet-async'
import { NeonAuthUIProvider } from '@neondatabase/auth-ui'
import { Toaster } from 'sonner'
import App from './App'
import { queryClient } from './lib/queryClient'
import { authClient, SESSION_QUERY_KEY } from './lib/neonAuth'
import '@neondatabase/auth-ui/css'
import './index.css'

/**
 * Wires Neon Auth UI into the app's router + query client. Must live inside
 * <BrowserRouter> and <QueryClientProvider> so it can use react-router
 * navigation and invalidate the cached session whenever auth state changes.
 */
function AuthProviders({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const reactQueryClient = useQueryClient()
  return (
    <NeonAuthUIProvider
      authClient={authClient}
      navigate={(href) => navigate(href)}
      replace={(href) => navigate(href, { replace: true })}
      Link={({ href, ...props }) => <Link to={href} {...props} />}
      onSessionChange={() =>
        reactQueryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY })
      }
    >
      {children}
    </NeonAuthUIProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HelmetProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <AuthProviders>
              <App />
              <Toaster position="bottom-left" richColors />
            </AuthProviders>
          </BrowserRouter>
        </QueryClientProvider>
    </HelmetProvider>
  </React.StrictMode>,
)
