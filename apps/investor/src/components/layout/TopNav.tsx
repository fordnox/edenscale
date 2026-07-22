import { useEffect, useRef, useState } from "react"
import { Link, NavLink, useNavigate } from "react-router-dom"
import { LogOut, Search, User as UserIcon } from "lucide-react"

import { BrandMark } from "@edenscale/brand/components/BrandMark"
import { cn } from "@edenscale/shared/utils"
import { deriveInitials } from "@edenscale/shared/userDisplay"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useAuth } from "@edenscale/auth/useAuth"
import { useOrgNavItems, type NavItem } from "@/hooks/useNavItems"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { orgPath } from "@/lib/investorRoutes"
import { OrganizationSwitcher } from "@/components/layout/Topbar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
import { ThemeToggle } from "@edenscale/ui/theme-toggle"
import { Kbd } from "@edenscale/ui/kbd"

interface TopNavProps {
  onOpenSearch?: () => void
}

// Which edges of a horizontally scrollable element have content hidden
// beyond them right now. Drives the fade overlays that signal "more here —
// scroll" on narrow screens.
function useScrollEdges<T extends HTMLElement>(contentKey: unknown) {
  const ref = useRef<T>(null)
  const [edges, setEdges] = useState({ left: false, right: false })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => {
      const maxScroll = el.scrollWidth - el.clientWidth
      // 1px slack absorbs fractional scroll positions on zoomed displays.
      setEdges({
        left: el.scrollLeft > 1,
        right: el.scrollLeft < maxScroll - 1,
      })
    }
    update()
    el.addEventListener("scroll", update, { passive: true })
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => {
      el.removeEventListener("scroll", update)
      observer.disconnect()
    }
    // contentKey re-measures when the rendered content changes (e.g. the
    // link list), which ResizeObserver alone won't see if the element's own
    // box size stays the same.
  }, [contentKey])

  return { ref, edges }
}

// The mark is the app's home affordance and is present in every state, so it
// works the same whether or not the org label next to it is a switcher.
// Destination is the top of the user's world: their one org's dashboard when
// they have exactly one, otherwise the cross-org root.
function BrandHomeLink() {
  const { organizations } = useInvestorOrganizations()
  const only = organizations.length === 1 ? organizations[0] : null
  const to = only ? orgPath(only.organization.slug) : "/investor"

  return (
    <Link
      to={to}
      aria-label="NewTaven investor portal — home"
      className={cn(
        "inline-flex shrink-0 items-center rounded-xs",
        "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
      )}
    >
      <BrandMark className="size-7 text-brass-700 transition-opacity duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)] hover:opacity-80" />
    </Link>
  )
}

// Horizontal top-bar navigation for the investor app — no sidebar. Tier 1 holds
// the brand mark, org switcher and the account menu; tier 2 holds the section
// links.
export function TopNav({ onOpenSearch }: TopNavProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { items } = useOrgNavItems()

  // The org-scoped section links only (drop the account-home item, dividers,
  // and section headings — the org switcher already covers "home").
  const links = items.filter(
    (e): e is NavItem =>
      e.kind !== "section" && e.kind !== "divider" && e.to !== "/investor",
  )

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

  const { ref: linksRef, edges } = useScrollEdges<HTMLUListElement>(
    links.length,
  )

  return (
    <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
      {/* Tier 1 — brand + org + account */}
      <div className="flex items-center gap-3 px-4 py-3 md:px-8">
        <BrandHomeLink />
        <OrganizationSwitcher />
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={onOpenSearch}
            aria-label="Open search"
            className={cn(
              "hidden items-center gap-2 rounded-xs border border-[color:var(--border-hairline)] px-3 py-1.5 sm:inline-flex",
              "font-sans text-[13px] text-ink-500 transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "hover:border-conifer-600 hover:text-ink-900",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
            )}
          >
            <Search strokeWidth={1.5} className="size-4" />
            <span>Search</span>
            <Kbd className="bg-parchment-200 text-ink-700">⌘K</Kbd>
          </button>

          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                "flex items-center gap-3 rounded-xs px-2 py-1.5 text-left",
                "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                "hover:bg-parchment-100",
                "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
              )}
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
              <div className="px-2 py-1.5">
                <div className="mb-1.5 font-sans text-[11px] font-medium text-ink-500">
                  Theme
                </div>
                <ThemeToggle />
              </div>
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

      {/* Tier 2 — section links (scroll horizontally on narrow screens).
          Edge fades appear only on the side(s) with clipped content, so the
          scrollability is visible without a scrollbar. */}
      <nav className="relative border-t border-[color:var(--border-hairline)]">
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-y-0 left-0 z-10 w-12",
            "bg-gradient-to-r from-[color:var(--color-page)] to-transparent",
            "opacity-0 transition-opacity duration-200",
            edges.left && "opacity-100",
          )}
        />
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-y-0 right-0 z-10 w-12",
            "bg-gradient-to-l from-[color:var(--color-page)] to-transparent",
            "opacity-0 transition-opacity duration-200",
            edges.right && "opacity-100",
          )}
        />
        <ul
          ref={linksRef}
          className="flex items-stretch gap-1 overflow-x-auto px-2 md:px-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {links.map(({ to, label, icon: Icon, end }) => (
            <li key={to} className="shrink-0">
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "group inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-3 text-left",
                    "font-sans text-[14px] transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                    isActive
                      ? "border-conifer-700 text-ink-900 font-medium"
                      : "border-transparent text-ink-500 hover:text-ink-900",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        "size-[17px] shrink-0",
                        isActive ? "text-conifer-700" : "text-ink-500",
                      )}
                      strokeWidth={1.5}
                    />
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  )
}
