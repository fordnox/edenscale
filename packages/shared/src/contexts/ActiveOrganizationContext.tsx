import { useMemo, createContext, type ReactNode } from "react"

import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import {
  OrgSelectionContext,
  useActiveOrganizationIdState,
  type OrgSelectionContextValue,
} from "@edenscale/shared/contexts/OrgSelectionContext"
import type { components } from "@edenscale/api/schema"

// TODO: tests pending frontend test harness setup

type MembershipRead = components["schemas"]["MembershipRead"]
type UserRole = components["schemas"]["UserRole"]

// Staff org context (manager / superadmin apps): organizations come from
// membership rows with real roles. The investor app doesn't use this — it
// has its own contact-link-based provider (InvestorOrganizationsContext in
// apps/investor); the two share only OrgSelectionContext.
export interface ActiveOrganizationContextValue {
  memberships: MembershipRead[]
  activeMembership: MembershipRead | null
  activeOrganizationId: string | null
  setActiveOrganizationId: (id: string | null) => void
  isSuperadmin: boolean
  isLoading: boolean
}

export const ActiveOrganizationContext =
  createContext<ActiveOrganizationContextValue | null>(null)

interface ActiveOrganizationProviderProps {
  children: ReactNode
  // The membership roles this app serves. When set, memberships (and pending
  // invitations — see usePendingInvitations) with other roles are invisible
  // to the app: each SPA only ever sees its own slice of the account, even
  // when the same login is an LP in one org and a manager in another.
  roles?: readonly UserRole[]
}

export function ActiveOrganizationProvider({
  children,
  roles,
}: ActiveOrganizationProviderProps) {
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const membershipsQuery = useApiQuery("/users/me/memberships", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const [activeOrganizationId, setActiveOrganizationId] =
    useActiveOrganizationIdState()

  const memberships = useMemo<MembershipRead[]>(() => {
    const all = membershipsQuery.data ?? []
    return roles ? all.filter((m) => roles.includes(m.role)) : all
  }, [membershipsQuery.data, roles])
  const isSuperadmin = meQuery.data?.is_superadmin === true

  const activeMembership = useMemo<MembershipRead | null>(
    () =>
      memberships.find((m) => m.organization_id === activeOrganizationId) ??
      null,
    [memberships, activeOrganizationId],
  )

  const isLoading = meQuery.isLoading || membershipsQuery.isLoading

  const value = useMemo<ActiveOrganizationContextValue>(
    () => ({
      memberships,
      activeMembership,
      activeOrganizationId,
      setActiveOrganizationId,
      isSuperadmin,
      isLoading,
    }),
    [
      memberships,
      activeMembership,
      activeOrganizationId,
      setActiveOrganizationId,
      isSuperadmin,
      isLoading,
    ],
  )

  const selectionValue = useMemo<OrgSelectionContextValue>(
    () => ({
      activeOrganizationId,
      setActiveOrganizationId,
      appRoles: roles ?? null,
      isLoading,
    }),
    [activeOrganizationId, setActiveOrganizationId, roles, isLoading],
  )

  return (
    <OrgSelectionContext.Provider value={selectionValue}>
      <ActiveOrganizationContext.Provider value={value}>
        {children}
      </ActiveOrganizationContext.Provider>
    </OrgSelectionContext.Provider>
  )
}
