import { useState } from "react"
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom"
import {
  Bell,
  Check,
  ChevronsUpDown,
  LogOut,
  Search,
  User as UserIcon,
} from "lucide-react"

import { BrandMark } from "@edenscale/brand/components/BrandMark"
import { cn } from "@edenscale/shared/utils"
import { fundPath, fundSlugFromPath, orgPath } from "@/lib/managerRoutes"
import { deriveInitials } from "@edenscale/shared/userDisplay"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useAuth } from "@edenscale/auth/useAuth"
import { useNavItems } from "@/hooks/useNavItems"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@edenscale/ui/command"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
import { ThemeToggle } from "@edenscale/ui/theme-toggle"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@edenscale/ui/popover"
import { Kbd } from "@edenscale/ui/kbd"
import { config } from "@edenscale/api/config"
import type { components } from "@edenscale/api/schema"

type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Partial<Record<UserRole, string>> = {
  admin: "Admin",
  fund_manager: "Fund manager",
  lp: "LP",
}

const STALE_FIVE_MIN = 5 * 60 * 1000

// Shared style for the small chevron button that opens a switcher dropdown
// next to a breadcrumb crumb.
const crumbChevronClass = cn(
  "inline-flex size-7 shrink-0 items-center justify-center rounded-xs",
  "text-ink-500 transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
  "hover:bg-parchment-200 hover:text-ink-900",
  "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
)

const crumbLinkClass = cn(
  "min-w-0 truncate rounded-xs px-1.5 py-1 font-sans text-[13px] font-medium text-ink-900",
  "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
  "hover:bg-parchment-100",
  "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
)

function CrumbSeparator() {
  return (
    <span
      aria-hidden
      className="mx-0.5 shrink-0 select-none font-sans text-[15px] font-light text-ink-500/40"
    >
      /
    </span>
  )
}

export interface TopbarOrganization {
  name: string
  slug: string
}

// Breadcrumb crumb for the organization level. Works without an active
// organization too (account-level pages): the crumb then reads "Select
// organization" and the switcher menu is the way into a workspace.
function OrgCrumb({
  organization,
  role,
}: {
  organization: TopbarOrganization | null
  role: UserRole | null
}) {
  const navigate = useNavigate()
  const { memberships, activeMembership } = useActiveOrganization()

  // With an org open the menu is for *switching* (needs somewhere else to
  // go); without one it is for *selecting* (any membership qualifies).
  const showMenu = memberships.length > (organization ? 1 : 0)

  if (!organization && !showMenu) return null

  return (
    <div className="flex min-w-0 items-center gap-0.5">
      <CrumbSeparator />
      {organization ? (
        <Link
          to={orgPath(organization.slug)}
          title={organization.name}
          className={cn(crumbLinkClass, "max-w-[180px]")}
        >
          {organization.name}
        </Link>
      ) : (
        <span className="px-1.5 py-1 font-sans text-[13px] font-medium text-ink-500">
          Select organization
        </span>
      )}
      {organization && role && (
        <span className="mx-1 hidden shrink-0 rounded-full border border-[color:var(--border-hairline)] px-2 py-0.5 font-sans text-[10px] tracking-[0.06em] uppercase text-ink-500 sm:inline-flex">
          {ROLE_LABELS[role]}
        </span>
      )}
      {showMenu && (
        <DropdownMenu>
          <DropdownMenuTrigger
            className={crumbChevronClass}
            aria-label="Switch organization"
          >
            <ChevronsUpDown strokeWidth={1.5} className="size-3.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            {memberships.length > 0 && (
              <>
                <DropdownMenuLabel className="text-[11px] tracking-[0.06em] text-ink-500 uppercase font-medium">
                  Organizations
                </DropdownMenuLabel>
                {memberships.map((m) => {
                  const isActive =
                    m.organization_id === activeMembership?.organization_id
                  return (
                    <DropdownMenuItem
                      key={m.id}
                      // Only navigate here — OrgLayout is the single place that
                      // calls setActiveOrganizationId, triggered by the
                      // resulting route change.
                      onSelect={() => navigate(orgPath(m.organization.slug))}
                      className="min-h-11 md:min-h-0 gap-3"
                    >
                      <span className="flex-1 min-w-0 truncate font-sans text-[13px] text-ink-900">
                        {m.organization.name}
                      </span>
                      <span className="shrink-0 font-sans text-[10px] tracking-[0.06em] uppercase text-ink-500">
                        {ROLE_LABELS[m.role]}
                      </span>
                      {isActive && (
                        <Check
                          strokeWidth={1.5}
                          className="size-4 shrink-0 text-conifer-700"
                        />
                      )}
                    </DropdownMenuItem>
                  )
                })}
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
}

// Second breadcrumb level: only rendered when a fund page is open. The name
// resolves via the same by-slug query FundLayout uses, so it comes from cache.
function FundCrumb({ orgSlug }: { orgSlug: string }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const fundSlug = fundSlugFromPath(pathname)

  const fundQuery = useApiQuery(
    "/funds/by-slug/{slug}",
    { params: { path: { slug: fundSlug ?? "" } } },
    { enabled: Boolean(fundSlug), retry: false },
  )
  const fundsQuery = useApiQuery("/funds", undefined, {
    enabled: open,
    staleTime: STALE_FIVE_MIN,
  })

  if (!fundSlug) return null

  const fundName = fundQuery.data?.name ?? fundSlug
  const funds = fundsQuery.data ?? []

  return (
    <>
      <CrumbSeparator />
      <div className="flex min-w-0 items-center gap-0.5">
        <Link
          to={fundPath(orgSlug, fundSlug)}
          title={fundName}
          className={cn(crumbLinkClass, "max-w-[180px]")}
        >
          {fundName}
        </Link>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            className={crumbChevronClass}
            aria-label="Switch fund"
          >
            <ChevronsUpDown strokeWidth={1.5} className="size-3.5" />
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64 p-0">
            <Command>
              <CommandInput placeholder="Search funds…" />
              <CommandList>
                <CommandEmpty>No funds found</CommandEmpty>
                <CommandGroup heading="Funds">
                  {funds.map((fund) => (
                    <CommandItem
                      key={fund.id}
                      value={`${fund.name} ${fund.slug}`}
                      onSelect={() => {
                        setOpen(false)
                        navigate(fundPath(orgSlug, fund.slug))
                      }}
                    >
                      <span className="flex-1 min-w-0 truncate">
                        {fund.name}
                      </span>
                      {fund.slug === fundSlug && (
                        <Check
                          strokeWidth={1.5}
                          className="size-4 shrink-0 text-conifer-700"
                        />
                      )}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
    </>
  )
}

function UserMenu() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const { data: me } = useApiQuery("/users/me", undefined, {
    staleTime: STALE_FIVE_MIN,
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
    navigate("/manager/login")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "inline-flex size-8 shrink-0 items-center justify-center rounded-xs",
          "bg-conifer-700 text-parchment-50 font-display text-[13px] font-medium",
          "transition-opacity duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)] hover:opacity-90",
          "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
        )}
        aria-label="Open user menu"
      >
        {initials}
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
        <div className="px-2 py-1.5">
          <div className="mb-1.5 font-sans text-[11px] font-medium text-ink-500">
            Theme
          </div>
          <ThemeToggle />
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="min-h-11 md:min-h-0"
          onSelect={() => navigate("/manager/notifications")}
        >
          <Bell strokeWidth={1.5} />
          <span>Notifications</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="min-h-11 md:min-h-0"
          onSelect={() => navigate("/manager/profile")}
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
  )
}

// Horizontal nav: every former sidebar item scoped to the current org (or the
// open fund's sections). The account dashboard is reachable via the logo.
function NavTabs({ orgSlug }: { orgSlug: string }) {
  const { items } = useNavItems()
  const orgRoot = orgPath(orgSlug)

  const tabs = items.filter(
    (entry): entry is Extract<typeof entry, { to: string }> =>
      entry.kind !== "section" &&
      entry.kind !== "divider" &&
      (entry.to === orgRoot || entry.to.startsWith(`${orgRoot}/`)),
  )

  return (
    <nav
      aria-label="Primary"
      className="flex items-center overflow-x-auto px-2 md:px-4 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {tabs.map(({ to, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "flex h-10 shrink-0 items-center whitespace-nowrap border-b-2 px-3",
              "font-sans text-[13px]",
              "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:-outline-offset-2",
              isActive
                ? "border-conifer-700 font-medium text-ink-900"
                : "border-transparent text-ink-700 hover:border-[color:var(--border-hairline)] hover:text-ink-900",
            )
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

interface TopbarProps {
  /** The open organization, or null on account-level pages (/manager,
   * /manager/profile, …) — the org switcher stays available either way. */
  organization?: TopbarOrganization | null
  role?: UserRole | null
  /** Omit to hide the search button (search is org-scoped). */
  onOpenSearch?: () => void
}

// The app-wide top bar: breadcrumb controls (logo / organization / fund) with
// switcher dropdowns, search and the user menu on the right, and a second row
// of nav tabs. Without an organization it degrades to the account variant:
// app title, org selector, user menu — no tabs, no search.
export function Topbar({
  organization = null,
  role = null,
  onOpenSearch,
}: TopbarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
      <div className="flex h-14 items-center gap-1 px-3 md:px-4">
        <Link
          to="/manager"
          aria-label="Account dashboard"
          className={cn(
            "mr-1 flex size-8 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700",
            "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)] hover:bg-parchment-100",
            "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
          )}
        >
          <BrandMark className="size-5" />
        </Link>
        {!organization && (
          <span className="ml-1 font-sans text-[14px] font-semibold tracking-[-0.04em] text-ink-900">
            {config.VITE_APP_TITLE}
          </span>
        )}
        <OrgCrumb organization={organization} role={role} />
        {organization && <FundCrumb orgSlug={organization.slug} />}

        <div className="ml-auto flex shrink-0 items-center gap-2 pl-2">
          {onOpenSearch && (
            <button
              type="button"
              onClick={onOpenSearch}
              aria-label="Open search"
              className={cn(
                "inline-flex h-8 items-center gap-2 rounded-xs border border-[color:var(--border-hairline)] bg-surface px-2.5",
                "text-ink-700 transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                "hover:border-conifer-600 hover:text-ink-900",
                "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
              )}
            >
              <Search strokeWidth={1.5} className="size-4" />
              <Kbd className="hidden bg-parchment-200 text-ink-700 md:inline-flex">
                ⌘K
              </Kbd>
            </button>
          )}
          <UserMenu />
        </div>
      </div>

      {organization && <NavTabs orgSlug={organization.slug} />}
    </header>
  )
}
