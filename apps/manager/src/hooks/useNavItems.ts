import { useMemo } from "react"
import { useLocation, useParams } from "react-router-dom"
import {
  ArrowDownToLine,
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
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import {
  fundPath,
  fundSectionPath,
  fundSlugFromPath,
  orgPath,
  type FundSection,
} from "@/lib/managerRoutes"
import type { components } from "@edenscale/api/schema"

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

const SUPERADMIN_ORGANIZATIONS_PATH = "/manager/superadmin/organizations"

function orgItems(orgSlug: string): NavItem[] {
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

/** Nav items for the organization-level workspace (/manager/:orgSlug/...). */
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
      to: "/manager",
      label: "Dashboard",
      icon: LayoutDashboard,
      end: true,
    }
    const tenantItems = orgSlug ? orgItems(orgSlug) : []
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
  }, [isSuperadmin, orgSlug])

  return { items, role, isLoading }
}

/** Nav items for the fund workspace (/manager/:orgSlug/:fundSlug) — each
 * fund section is its own page under the fund route. */
export function useFundNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const params = useParams<{ orgSlug?: string }>()
  const { pathname } = useLocation()
  const role = activeMembership?.role ?? null

  // The Sidebar renders at the /manager/:orgSlug route level, so useParams never
  // exposes the deeper :fundSlug — derive it from the URL instead.
  const orgSlug = params.orgSlug ?? activeMembership?.organization.slug
  const fundSlug = fundSlugFromPath(pathname)

  const items = useMemo<NavEntry[]>(() => {
    if (!orgSlug || !fundSlug) return []

    const sectionItem = (
      section: FundSection,
      label: string,
      icon: NavItem["icon"],
    ): NavItem => ({ to: fundSectionPath(orgSlug, fundSlug, section), label, icon })

    return [
      {
        to: fundPath(orgSlug, fundSlug),
        label: "Overview",
        icon: LayoutDashboard,
        end: true,
      },
      sectionItem("commitments", "Commitments", Users),
      sectionItem("calls", "Capital Calls", ArrowDownToLine),
      sectionItem("distributions", "Distributions", ArrowUpFromLine),
      sectionItem("team", "Team", UserCog),
      sectionItem("letters", "Letters", Mail),
    ]
  }, [orgSlug, fundSlug])

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
