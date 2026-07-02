import { useMemo } from "react"
import { useLocation, useParams } from "react-router-dom"
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowUpFromLine,
  Bell,
  Building2,
  ClipboardCheck,
  FileText,
  History,
  Layers,
  LayoutDashboard,
  Mail,
  UserCog,
  Users,
} from "lucide-react"

import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@/hooks/useApiQuery"
import { fundPath, fundSlugFromPath, fundTabPath, orgPath } from "@/lib/appRoutes"
import type { components } from "@/lib/schema"

type UserRole = components["schemas"]["UserRole"]

export interface NavItem {
  kind?: "item"
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
}

export interface NavSection {
  kind: "section"
  label: string
}

export interface NavDivider {
  kind: "divider"
}

export type NavEntry = NavItem | NavSection | NavDivider

const SUPERADMIN_ORGANIZATIONS_PATH = "/app/superadmin/organizations"

function orgItemsForRole(role: UserRole | null | undefined, orgSlug: string): NavItem[] {
  const overview: NavItem = {
    to: orgPath(orgSlug),
    label: "Overview",
    icon: LayoutDashboard,
    end: true,
  }
  const funds: NavItem = { to: orgPath(orgSlug, "funds"), label: "Funds", icon: Layers }
  const investors: NavItem = {
    to: orgPath(orgSlug, "investors"),
    label: "Investors",
    icon: Users,
  }
  const calls: NavItem = {
    to: orgPath(orgSlug, "calls"),
    label: "Capital Calls",
    icon: ArrowDownToLine,
  }
  const distributions: NavItem = {
    to: orgPath(orgSlug, "distributions"),
    label: "Distributions",
    icon: ArrowUpFromLine,
  }
  const documents: NavItem = {
    to: orgPath(orgSlug, "documents"),
    label: "Documents",
    icon: FileText,
  }
  const letters: NavItem = { to: orgPath(orgSlug, "letters"), label: "Letters", icon: Mail }
  const tasks: NavItem = {
    to: orgPath(orgSlug, "tasks"),
    label: "Tasks",
    icon: ClipboardCheck,
  }
  const notifications: NavItem = {
    to: orgPath(orgSlug, "notifications"),
    label: "Notifications",
    icon: Bell,
  }
  const auditLog: NavItem = {
    to: orgPath(orgSlug, "audit-log"),
    label: "Audit Log",
    icon: History,
  }

  if (role === "lp") {
    // LPs see their own slice of everything: the funds they hold commitments
    // in, their capital calls and distributions, and the investor record(s)
    // they are a linked contact for (the backend scopes the register).
    return [
      overview,
      funds,
      investors,
      calls,
      distributions,
      documents,
      letters,
      notifications,
    ]
  }
  return [
    overview,
    funds,
    investors,
    calls,
    distributions,
    documents,
    letters,
    tasks,
    notifications,
    auditLog,
  ]
}

interface UseNavItemsResult {
  items: NavEntry[]
  role: UserRole | null
  isLoading: boolean
}

/** Nav items for the organization-level workspace (/app/:orgSlug/...). */
export function useOrgNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const params = useParams<{ orgSlug?: string }>()
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const isSuperadmin = meQuery.data?.role === "superadmin"

  const role = activeMembership?.role ?? null
  const orgSlug = params.orgSlug ?? activeMembership?.organization.slug ?? null

  const items = useMemo<NavEntry[]>(() => {
    const homeItem: NavItem = {
      to: "/app",
      label: "Dashboard",
      icon: LayoutDashboard,
      end: true,
    }
    const tenantItems = orgSlug ? orgItemsForRole(role, orgSlug) : []
    if (!isSuperadmin) {
      return orgSlug ? [homeItem, { kind: "divider" }, ...tenantItems] : [homeItem]
    }

    const superadminEntries: NavEntry[] = [
      homeItem,
      { kind: "divider" },
      { kind: "section", label: "Superadmin" },
      {
        to: SUPERADMIN_ORGANIZATIONS_PATH,
        label: "Organizations",
        icon: Building2,
      },
    ]
    if (tenantItems.length === 0) return superadminEntries
    return [...superadminEntries, { kind: "divider" }, ...tenantItems]
  }, [role, isSuperadmin, orgSlug])

  return { items, role, isLoading }
}

/** Nav items for the fund workspace (/app/:orgSlug/:fundSlug) — links set
 * the ?tab= query param on the existing fund detail page rather than
 * navigating to separate routes. */
export function useFundNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const params = useParams<{ orgSlug?: string }>()
  const { pathname } = useLocation()
  const role = activeMembership?.role ?? null

  // The Sidebar renders at the /app/:orgSlug route level, so useParams never
  // exposes the deeper :fundSlug — derive it from the URL instead.
  const orgSlug = params.orgSlug ?? activeMembership?.organization.slug
  const fundSlug = fundSlugFromPath(pathname)

  const items = useMemo<NavEntry[]>(() => {
    if (!orgSlug || !fundSlug) return []

    const tabItem = (
      tab: "commitments" | "calls" | "distributions" | "team" | "letters",
      label: string,
      icon: NavItem["icon"],
    ): NavItem => ({ to: fundTabPath(orgSlug, fundSlug, tab), label, icon })

    return [
      {
        to: fundPath(orgSlug, fundSlug),
        label: "Overview",
        icon: LayoutDashboard,
        end: true,
      },
      tabItem("commitments", "Commitments", Users),
      tabItem("calls", "Capital Calls", ArrowDownToLine),
      tabItem("distributions", "Distributions", ArrowUpFromLine),
      tabItem("team", "Team", UserCog),
      tabItem("letters", "Letters", Mail),
      { kind: "divider" },
      {
        to: orgPath(orgSlug),
        label: `Back to ${activeMembership?.organization.name ?? "organization"}`,
        icon: ArrowLeft,
      },
    ]
  }, [orgSlug, fundSlug, activeMembership])

  return { items, role, isLoading }
}

/** Dispatches between org- and fund-scoped nav based on the URL: a third
 * path segment that isn't a static org route (see fundSlugFromPath) means a
 * fund page is open. The Sidebar renders above the :fundSlug route, so we
 * read the path rather than useParams (which wouldn't expose fundSlug). */
export function useNavItems(): UseNavItemsResult {
  const { pathname } = useLocation()
  const orgItems = useOrgNavItems()
  const fundItems = useFundNavItems()
  return fundSlugFromPath(pathname) ? fundItems : orgItems
}
