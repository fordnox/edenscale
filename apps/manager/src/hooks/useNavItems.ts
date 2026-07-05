import { useMemo } from "react"
import { useLocation, useParams } from "react-router-dom"
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ClipboardCheck,
  FileText,
  History,
  Layers,
  LayoutDashboard,
  Mail,
  Settings,
  Users,
} from "lucide-react"

import { useActiveOrganization } from "@/hooks/useActiveOrganization"
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

// Settings pages are for roles that can manage the workspace — mirrors the
// canManage checks in OrgLayout/FundLayout.
function canManageSettings(role: UserRole | null): boolean {
  return role === "admin" || role === "fund_manager" || role === "superadmin"
}

function orgItems(orgSlug: string, role: UserRole | null): NavItem[] {
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
  const auditLog: NavItem = {
    to: orgPath(orgSlug, "audit-log"),
    label: "Audit Log",
    icon: History,
  }
  const settings: NavItem = {
    to: orgPath(orgSlug, "settings"),
    label: "Settings",
    icon: Settings,
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
    auditLog,
    ...(canManageSettings(role) ? [settings] : []),
  ]
}

interface UseNavItemsResult {
  items: NavEntry[]
  role: UserRole | null
  isLoading: boolean
}

/** Nav items for the organization-level workspace (/manager/:orgSlug/...).
 * Superadmin pages live in the separate /superadmin SPA, so there is no
 * superadmin section here. */
export function useOrgNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const params = useParams<{ orgSlug?: string }>()

  const role = activeMembership?.role ?? null
  const orgSlug = params.orgSlug ?? activeMembership?.organization.slug ?? null

  const items = useMemo<NavEntry[]>(() => {
    const homeItem: NavItem = {
      to: "/manager",
      label: "Dashboard",
      icon: LayoutDashboard,
      end: true,
    }
    const tenantItems = orgSlug ? orgItems(orgSlug, role) : []
    return orgSlug ? [homeItem, { kind: "divider" }, ...tenantItems] : [homeItem]
  }, [orgSlug, role])

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
      sectionItem("letters", "Letters", Mail),
      ...(canManageSettings(role)
        ? [sectionItem("settings", "Settings", Settings)]
        : []),
    ]
  }, [orgSlug, fundSlug, role])

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
