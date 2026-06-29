import { useMemo } from "react"
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
  Users,
} from "lucide-react"

import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@/hooks/useApiQuery"
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

const OVERVIEW: NavItem = { to: "/", label: "Overview", icon: LayoutDashboard, end: true }
const FUNDS: NavItem = { to: "/funds", label: "Funds", icon: Layers }
const INVESTORS: NavItem = { to: "/investors", label: "Investors", icon: Users }
const CALLS: NavItem = { to: "/calls", label: "Capital Calls", icon: ArrowDownToLine }
const DISTRIBUTIONS: NavItem = {
  to: "/distributions",
  label: "Distributions",
  icon: ArrowUpFromLine,
}
const DOCUMENTS: NavItem = { to: "/documents", label: "Documents", icon: FileText }
const LETTERS: NavItem = { to: "/letters", label: "Letters", icon: Mail }
const TASKS: NavItem = { to: "/tasks", label: "Tasks", icon: ClipboardCheck }
const NOTIFICATIONS: NavItem = { to: "/notifications", label: "Notifications", icon: Bell }
const AUDIT_LOG: NavItem = { to: "/audit-log", label: "Audit Log", icon: History }

const SUPERADMIN_ORGANIZATIONS: NavItem = {
  to: "/superadmin/organizations",
  label: "Organizations",
  icon: Building2,
}

const FULL_ITEMS: NavItem[] = [
  OVERVIEW,
  FUNDS,
  INVESTORS,
  CALLS,
  DISTRIBUTIONS,
  DOCUMENTS,
  LETTERS,
  TASKS,
  NOTIFICATIONS,
]

const LP_ITEMS: NavItem[] = [
  OVERVIEW,
  FUNDS,
  INVESTORS,
  DOCUMENTS,
  LETTERS,
  NOTIFICATIONS,
]

export function navItemsForRole(role: UserRole | null | undefined): NavItem[] {
  if (role === "lp") return LP_ITEMS
  if (role === "admin") return [...FULL_ITEMS, AUDIT_LOG]
  return FULL_ITEMS
}

interface UseNavItemsResult {
  items: NavEntry[]
  role: UserRole | null
  isLoading: boolean
}

export function useNavItems(): UseNavItemsResult {
  const { activeMembership, isLoading } = useActiveOrganization()
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const isSuperadmin = meQuery.data?.role === "superadmin"

  const role = activeMembership?.role ?? null

  const items = useMemo<NavEntry[]>(() => {
    const tenantItems = navItemsForRole(role)
    if (!isSuperadmin) return tenantItems

    const superadminEntries: NavEntry[] = [
      { kind: "section", label: "Superadmin" },
      SUPERADMIN_ORGANIZATIONS,
    ]
    if (tenantItems.length === 0) return superadminEntries
    return [
      ...superadminEntries,
      { kind: "divider" },
      ...tenantItems,
    ]
  }, [role, isSuperadmin])

  return { items, role, isLoading }
}
