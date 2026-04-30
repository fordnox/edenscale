import { Bell, LogOut, Search, User as UserIcon } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { useApiQuery } from "@/hooks/useApiQuery"
import { useAuth } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function deriveInitials(first?: string | null, last?: string | null, email?: string | null) {
  const f = (first ?? "").trim()
  const l = (last ?? "").trim()
  if (f && l) return (f[0] + l[0]).toUpperCase()
  if (f.length >= 2) return f.slice(0, 2).toUpperCase()
  const local = (email ?? "").split("@")[0] ?? ""
  const parts = local.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (local.slice(0, 2) || "ES").toUpperCase()
}

export function Topbar() {
  const navigate = useNavigate()
  const { logout } = useAuth()

  const { data: me } = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const { data: notifications } = useApiQuery(
    "/notifications",
    { params: { query: { limit: 200 } } },
    { staleTime: 60 * 1000 },
  )

  const unreadCount = (notifications ?? []).filter(
    (n) => n.status === "unread",
  ).length
  const hasUnread = unreadCount > 0
  const badgeLabel = unreadCount > 99 ? "99+" : String(unreadCount)

  const fullName = [me?.first_name, me?.last_name].filter(Boolean).join(" ").trim()
  const displayName = fullName || me?.email || "Signed in"
  const initials = deriveInitials(me?.first_name, me?.last_name, me?.email)

  const handleSignOut = async () => {
    await logout()
    navigate("/login")
  }

  return (
    <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
      <div className="flex items-center justify-between gap-6 px-8 py-4">
        <div className="relative hidden md:block">
          <Search
            strokeWidth={1.5}
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-500"
          />
          <input
            type="search"
            placeholder="Search funds, investors, documents…"
            className="h-9 w-[340px] rounded-xs border border-[color:var(--border-hairline)] bg-surface pl-9 pr-3 font-sans text-[13px] text-ink-900 placeholder:text-ink-500 focus:border-conifer-600 focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/notifications"
            aria-label={
              hasUnread
                ? `Notifications (${unreadCount} unread)`
                : "Notifications"
            }
            className={cn(
              "relative inline-flex size-9 items-center justify-center rounded-xs",
              "text-ink-700 transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "hover:bg-parchment-200 hover:text-ink-900",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
            )}
          >
            <Bell strokeWidth={1.5} className="size-[18px]" />
            {hasUnread && (
              <span
                className={cn(
                  "absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full",
                  "bg-brass-500 px-1 font-sans text-[10px] font-medium leading-none text-parchment-50",
                )}
              >
                {badgeLabel}
              </span>
            )}
          </Link>

          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                "inline-flex items-center gap-2 rounded-xs px-2 py-1.5",
                "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                "hover:bg-parchment-200",
                "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
              )}
              aria-label="Open user menu"
            >
              <span className="inline-flex size-8 items-center justify-center bg-conifer-700 text-parchment-50 font-display text-[13px] font-medium">
                {initials}
              </span>
              <span className="hidden flex-col items-start leading-tight md:flex">
                <span className="font-sans text-[13px] font-medium text-ink-900 max-w-[160px] truncate">
                  {displayName}
                </span>
                {me?.title && (
                  <span className="font-sans text-[11px] text-ink-500 max-w-[160px] truncate">
                    {me.title}
                  </span>
                )}
              </span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="flex flex-col gap-0.5">
                <span className="font-sans text-[13px] font-medium text-ink-900 truncate">
                  {displayName}
                </span>
                {me?.email && (
                  <span className="font-sans text-[11px] text-ink-500 truncate">
                    {me.email}
                  </span>
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => navigate("/profile")}>
                <UserIcon strokeWidth={1.5} />
                <span>Profile</span>
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={handleSignOut}>
                <LogOut strokeWidth={1.5} />
                <span>Sign out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
