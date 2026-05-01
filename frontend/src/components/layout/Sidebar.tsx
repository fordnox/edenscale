import { useEffect } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { LogOut, Search, Settings, User as UserIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useApiQuery } from "@/hooks/useApiQuery"
import { useAuth } from "@/hooks/useAuth"
import { useNavItems } from "@/hooks/useNavItems"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Drawer,
  DrawerContent,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer"
import { Kbd } from "@/components/ui/kbd"

function deriveInitials(
  first?: string | null,
  last?: string | null,
  email?: string | null,
) {
  const f = (first ?? "").trim()
  const l = (last ?? "").trim()
  if (f && l) return (f[0] + l[0]).toUpperCase()
  if (f.length >= 2) return f.slice(0, 2).toUpperCase()
  const local = (email ?? "").split("@")[0] ?? ""
  const parts = local.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (local.slice(0, 2) || "ES").toUpperCase()
}

const ROLE_TAGLINES: Record<string, string> = {
  admin: "Administrator view",
  fund_manager: "Manager view",
  lp: "Limited partner view",
}

interface SidebarBodyProps {
  onOpenSearch?: () => void
  onCloseSheet?: () => void
}

function SidebarBody({ onOpenSearch, onCloseSheet }: SidebarBodyProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { items, role } = useNavItems()
  const tagline = (role && ROLE_TAGLINES[role]) ?? "Manager view"

  const handleSearchClick = () => {
    onCloseSheet?.()
    onOpenSearch?.()
  }

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
    navigate("/login")
  }

  return (
    <>
      <div className="flex items-center gap-3 px-6 pt-7 pb-6">
        <span className="inline-flex size-7 items-center justify-center text-conifer-700">
          <svg viewBox="0 0 64 64" className="size-7" aria-hidden="true">
            <path
              fill="currentColor"
              fillRule="evenodd"
              clipRule="evenodd"
              d="M32 4 C 18 12, 10 24, 10 36 C 10 49, 20 60, 32 60 C 44 60, 54 49, 54 36 C 54 24, 46 12, 32 4 Z M32 50 L 32 30 L 26 30 L 32 22 L 38 30 L 32 30 L 32 50 Z"
            />
          </svg>
        </span>
        <div className="flex flex-col leading-tight">
          <span className="font-sans text-[16px] font-semibold tracking-[-0.04em] text-ink-900">
            EdenScale
          </span>
          <span className="font-sans text-[11px] tracking-[0.04em] text-ink-500">
            LP portal · {tagline}
          </span>
        </div>
      </div>

      <hr className="es-rule mx-6" />

      <nav className="flex-1 px-3 py-5">
        <ul className="flex flex-col gap-0.5">
          <li>
            <button
              type="button"
              onClick={handleSearchClick}
              className={cn(
                "group flex w-full min-h-11 md:min-h-0 items-center gap-3 rounded-xs px-3 py-3 md:py-2.5 text-left",
                "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                "font-sans text-[14px] text-ink-700 hover:bg-parchment-100 hover:text-ink-900",
                "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
              )}
              aria-label="Open search"
            >
              <Search
                className="size-[18px] shrink-0 text-ink-500"
                strokeWidth={1.5}
              />
              <span className="flex-1">Search</span>
              <Kbd className="bg-parchment-200 text-ink-700">⌘K</Kbd>
            </button>
          </li>
          {items.map((entry, index) => {
            if (entry.kind === "section") {
              return (
                <li
                  key={`section-${entry.label}-${index}`}
                  className="px-3 pt-3 pb-1.5"
                >
                  <span className="font-sans text-[10px] font-semibold tracking-[0.08em] uppercase text-ink-500">
                    {entry.label}
                  </span>
                </li>
              )
            }
            if (entry.kind === "divider") {
              return (
                <li key={`divider-${index}`} className="py-2">
                  <hr className="es-rule mx-3" />
                </li>
              )
            }
            const { to, label, icon: Icon, end } = entry
            return (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "group flex w-full min-h-11 md:min-h-0 items-center gap-3 rounded-xs px-3 py-3 md:py-2.5 text-left",
                      "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                      "font-sans text-[14px]",
                      isActive
                        ? "bg-parchment-200 text-ink-900 font-medium"
                        : "text-ink-700 hover:bg-parchment-100 hover:text-ink-900",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon
                        className={cn(
                          "size-[18px] shrink-0",
                          isActive ? "text-conifer-700" : "text-ink-500",
                        )}
                        strokeWidth={1.5}
                      />
                      <span>{label}</span>
                    </>
                  )}
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>

      <hr className="es-rule mx-6" />

      <div className="px-3 py-3">
        <DropdownMenu>
          <DropdownMenuTrigger
            className={cn(
              "flex w-full min-h-11 items-center gap-3 rounded-xs px-3 py-2.5 text-left",
              "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "hover:bg-parchment-100",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
            )}
            aria-label="Open user menu"
          >
            <span className="inline-flex size-9 shrink-0 items-center justify-center bg-conifer-700 text-parchment-50 font-display text-base font-medium">
              {initials}
            </span>
            <span className="flex min-w-0 flex-col items-start leading-tight">
              <span className="max-w-full truncate font-sans text-[13px] font-medium text-ink-900">
                {displayName}
              </span>
              <span className="max-w-full truncate font-sans text-[11px] text-ink-500">
                {tagline}
              </span>
            </span>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-56">
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
              onSelect={() => navigate("/profile")}
            >
              <UserIcon strokeWidth={1.5} />
              <span>Profile</span>
            </DropdownMenuItem>
            {role === "admin" && (
              <DropdownMenuItem
                className="min-h-11 md:min-h-0"
                onSelect={() => navigate("/settings/organization")}
              >
                <Settings strokeWidth={1.5} />
                <span>Organization settings</span>
              </DropdownMenuItem>
            )}
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
    </>
  )
}

interface SidebarProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  onOpenSearch?: () => void
}

export function Sidebar({
  open = false,
  onOpenChange,
  onOpenSearch,
}: SidebarProps) {
  const location = useLocation()

  useEffect(() => {
    onOpenChange?.(false)
  }, [location.pathname, onOpenChange])

  const closeSheet = () => onOpenChange?.(false)

  return (
    <>
      <aside className="sticky top-0 hidden h-svh w-[260px] shrink-0 flex-col border-r border-[color:var(--border-hairline)] bg-page md:flex">
        <SidebarBody onOpenSearch={onOpenSearch} onCloseSheet={closeSheet} />
      </aside>

      <Drawer open={open} onOpenChange={onOpenChange} direction="left">
        <DrawerContent
          className={cn(
            "bg-page w-[280px] sm:w-[320px] sm:max-w-none border-l-0 border-r border-[color:var(--border-hairline)] shadow-xl pb-[env(safe-area-inset-bottom)] outline-none md:hidden",
          )}
        >
          <DrawerTitle className="sr-only">Navigation</DrawerTitle>
          <DrawerDescription className="sr-only">
            Primary navigation menu
          </DrawerDescription>
          <div className="flex h-full flex-col">
            <SidebarBody
              onOpenSearch={onOpenSearch}
              onCloseSheet={closeSheet}
            />
          </div>
        </DrawerContent>
      </Drawer>
    </>
  )
}
