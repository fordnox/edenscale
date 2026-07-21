import { Navigate, Outlet, useLocation } from "react-router-dom"
import { Loader2 } from "lucide-react"
import { useAuth } from "@edenscale/auth/useAuth"

interface ProtectedLayoutProps {
  loginPath: string
}

export function ProtectedLayout({ loginPath }: ProtectedLayoutProps) {
  const { isLoading, isAuthenticated } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </main>
    )
  }

  if (!isAuthenticated) {
    const next = `${location.pathname}${location.search}${location.hash}`
    return (
      <Navigate
        to={`${loginPath}?next=${encodeURIComponent(next)}`}
        replace
        state={{ from: location }}
      />
    )
  }

  return <Outlet />
}
