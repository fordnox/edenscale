import { useEffect } from "react"
import { NavLink, useLocation, useNavigate } from "react-router-dom"
import { LogOut, Search, User as UserIcon } from "lucide-react"

import { cn } from "@edenscale/shared/utils"
import { deriveInitials } from "@edenscale/shared/userDisplay"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useAuth } from "@edenscale/auth/useAuth"
import { useNavItems } from "@/hooks/useNavItems"
import { OrganizationSwitcher } from "@/components/layout/Topbar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
import {
  Drawer,
  DrawerContent,
  DrawerTitle,
  DrawerDescription,
} from "@edenscale/ui/drawer"
import { Kbd } from "@edenscale/ui/kbd"

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
  const tagline = (role && ROLE_TAGLINES[role]) ?? "Investor view"

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
      <div className="px-6 pt-7 pb-6">
        <OrganizationSwitcher />
      </div>

      <hr className="es-rule mx-6" />

      <nav className="flex-1 px-3 py-5">
        <ul className="flex flex-col gap-0.5">
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
