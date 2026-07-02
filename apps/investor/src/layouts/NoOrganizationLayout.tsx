import { Outlet, useNavigate } from "react-router-dom"
import { Landmark, LogOut, User as UserIcon } from "lucide-react"

import { PendingInvitationsBanner } from "@edenscale/ui/invitations/PendingInvitationsBanner"
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
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
import { config } from "@edenscale/api/config"
import { deriveInitials } from "@edenscale/shared/userDisplay"

export default function NoOrganizationLayout() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { visibleInvitations, showBanner, dismissBanner } =
    usePendingInvitations()

  const { data: me } = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const fullName = [me?.first_name, me?.last_name]
    .filter(Boolean)
    .join(" ")
    .trim()
  const email = me?.email ?? user?.email ?? null
  const displayName = fullName || email || "Signed in"
  const initials = deriveInitials(me?.first_name, me?.last_name, email)

  const handleSignOut = async () => {
    await logout()
    navigate("/investor/login")
  }

  return (
    <div className="flex min-h-svh flex-col bg-page text-ink-900">
      {showBanner && (
        <PendingInvitationsBanner
          invitations={visibleInvitations}
          onDismiss={dismissBanner}
          emphasize
        />
      )}
      <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
        <div className="flex items-center gap-3 px-4 py-3 md:px-8 md:py-4">
          <span className="flex size-9 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
            <Landmark strokeWidth={1.5} className="size-5" />
          </span>
          <span className="font-sans text-[16px] font-semibold tracking-[-0.04em] text-ink-900">
            {config.VITE_APP_TITLE}
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
                  onSelect={() => navigate("/investor/profile")}
                >
                  <UserIcon strokeWidth={1.5} />
                  <span>Profile</span>
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
      </header>
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
