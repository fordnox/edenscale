import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"
import {
  Building2,
  ExternalLink,
  Landmark,
  Loader2,
  LogOut,
  Users,
} from "lucide-react"

import { cn } from "@edenscale/shared/utils"
import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useAuth } from "@edenscale/auth/useAuth"
import { config } from "@edenscale/api/config"
import { deriveInitials } from "@edenscale/shared/userDisplay"

// Chrome for the whole control surface: slim header plus the superadmin role
// gate — every routed page renders through the Outlet only after /users/me
// confirms the global superadmin role.
const NAV_LINKS = [
  {
    to: "/superadmin",
    label: "Organizations",
    icon: Building2,
    // Org detail pages live under /superadmin/organizations/:id.
    isActive: (pathname: string) =>
      pathname === "/superadmin" ||
      pathname.startsWith("/superadmin/organizations"),
  },
  {
    to: "/superadmin/users",
    label: "Users",
    icon: Users,
    isActive: (pathname: string) => pathname.startsWith("/superadmin/users"),
  },
]

export default function SuperadminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const me = meQuery.data

  const fullName = [me?.first_name, me?.last_name]
    .filter(Boolean)
    .join(" ")
    .trim()
  const email = me?.email ?? user?.email ?? null
  const displayName = fullName || email || "Signed in"
  const initials = deriveInitials(me?.first_name, me?.last_name, email)

  const handleSignOut = async () => {
    await logout()
    navigate("/superadmin/login")
  }

  return (
    <div className="flex min-h-svh flex-col bg-page text-ink-900">
      <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
        <div className="flex items-center gap-3 px-4 py-3 md:px-8 md:py-4">
          <span className="flex size-9 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
            <Landmark strokeWidth={1.5} className="size-5" />
          </span>
          <span className="font-sans text-[16px] font-semibold tracking-[-0.04em] text-ink-900">
            {config.VITE_APP_TITLE}
          </span>
          <span className="rounded-full border border-[color:var(--border-hairline)] px-2 py-0.5 font-sans text-[10px] tracking-[0.06em] uppercase text-ink-500">
            Superadmin
          </span>

          <div className="ml-auto flex items-center">
            <DropdownMenu>
              <DropdownMenuTrigger
                className="flex items-center gap-3 rounded-xs px-2 py-1.5 text-left transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)] hover:bg-parchment-100 focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2"
                aria-label="Open user menu"
              >
                <span className="inline-flex size-9 shrink-0 items-center justify-center bg-conifer-700 text-parchment-50 font-display text-base font-medium">
                  {initials}
                </span>
                <span className="hidden max-w-[160px] truncate font-sans text-[13px] font-medium text-ink-900 md:inline">
                  {displayName}
                </span>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="bottom" align="end" className="w-56">
                <DropdownMenuLabel className="flex flex-col gap-0.5">
                  <span className="truncate font-sans text-[13px] font-medium text-ink-900">
                    {displayName}
                  </span>
                  {email && (
                    <span className="truncate font-sans text-[11px] font-normal text-ink-500">
                      {email}
                    </span>
                  )}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="min-h-11 md:min-h-0"
                  // Separate SPA — needs a full document navigation, not a
                  // client-side route change.
                  onSelect={() => window.location.assign("/manager")}
                >
                  <ExternalLink strokeWidth={1.5} />
                  <span>Manager app</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="min-h-11 md:min-h-0"
                  onSelect={handleSignOut}
                >
                  <LogOut strokeWidth={1.5} />
                  <span>Sign out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <nav aria-label="Superadmin sections">
          <ul className="flex items-stretch gap-1 overflow-x-auto px-2 md:px-6">
            {NAV_LINKS.map(({ to, label, icon: Icon, isActive }) => {
              const active = isActive(location.pathname)
              return (
                <li key={to} className="shrink-0">
                  <Link
                    to={to}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-3 text-left",
                      "font-sans text-[14px] transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                      active
                        ? "border-conifer-700 text-ink-900 font-medium"
                        : "border-transparent text-ink-500 hover:text-ink-900",
                    )}
                  >
                    <Icon
                      className={cn(
                        "size-[17px] shrink-0",
                        active ? "text-conifer-700" : "text-ink-500",
                      )}
                      strokeWidth={1.5}
                    />
                    <span>{label}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
      </header>
      <main className="flex flex-1 flex-col">
        {meQuery.isLoading ? (
          <div className="flex min-h-[280px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : !me?.is_superadmin ? (
          <div className="px-8 py-16">
            <Card>
              <EmptyState
                title="You do not have access to this area"
                body="The superadmin console is reserved for platform superadmins. Contact a superadmin if you need access."
                action={
                  <Button asChild variant="secondary" size="sm">
                    <a href="/manager">Go to manager app</a>
                  </Button>
                }
              />
            </Card>
          </div>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  )
}
