import { useMemo } from "react"
import { useLocation, useParams } from "react-router-dom"
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowUpFromLine,
  Bell,
  FileBarChart,
  FileText,
  Layers,
  LayoutDashboard,
  Mail,
} from "lucide-react"

import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { fundPath, fundSlugFromPath, orgPath } from "@/lib/investorRoutes"
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

interface UseNavItemsResult {
  items: NavEntry[]
  role: UserRole | null
  isLoading: boolean
}

function orgItems(orgSlug: string): NavItem[] {
  return [
    { to: orgPath(orgSlug), label: "Overview", icon: LayoutDashboard, end: true },
    { to: orgPath(orgSlug, "funds"), label: "Funds", icon: Layers },
    { to: orgPath(orgSlug, "calls"), label: "Capital Calls", icon: ArrowDownToLine },
    { to: orgPath(orgSlug, "distributions"), label: "Distributions", icon: ArrowUpFromLine },
    { to: orgPath(orgSlug, "reports"), label: "Reports", icon: FileBarChart },
    { to: orgPath(orgSlug, "documents"), label: "Documents", icon: FileText },
    { to: orgPath(orgSlug, "letters"), label: "Letters", icon: Mail },
    { to: orgPath(orgSlug, "notifications"), label: "Notifications", icon: Bell },
  ]
}

export function useOrgNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const params = useParams<{ orgSlug?: string }>()
  const role = activeMembership?.role ?? null
  const orgSlug = params.orgSlug ?? activeMembership?.organization.slug ?? null

  const items = useMemo<NavEntry[]>(() => {
    const homeItem: NavItem = {
      to: "/investor",
      label: "Dashboard",
      icon: LayoutDashboard,
      end: true,
    }
    return orgSlug ? [homeItem, { kind: "divider" }, ...orgItems(orgSlug)] : [homeItem]
  }, [orgSlug])

  return { items, role, isLoading }
}

export function useFundNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const params = useParams<{ orgSlug?: string }>()
  const { pathname } = useLocation()
  const role = activeMembership?.role ?? null
  const orgSlug = params.orgSlug ?? activeMembership?.organization.slug
  const fundSlug = fundSlugFromPath(pathname)

  const items = useMemo<NavEntry[]>(() => {
    if (!orgSlug || !fundSlug) return []
    return [
      {
        to: fundPath(orgSlug, fundSlug),
        label: "Overview",
        icon: LayoutDashboard,
        end: true,
      },
      { kind: "divider" },
      {
        to: orgPath(orgSlug, "funds"),
        label: `Back to ${activeMembership?.organization.name ?? "funds"}`,
        icon: ArrowLeft,
      },
    ]
  }, [orgSlug, fundSlug, activeMembership])

  return { items, role, isLoading }
}

export function useInvestorNavItems(): UseNavItemsResult {
  const { pathname } = useLocation()
  const orgItems = useOrgNavItems()
  const fundItems = useFundNavItems()
  return fundSlugFromPath(pathname) ? fundItems : orgItems
}

export function useNavItems(): UseNavItemsResult {
  return useInvestorNavItems()
}
