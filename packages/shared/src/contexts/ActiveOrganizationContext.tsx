import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useQueryClient } from "@tanstack/react-query"

import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import {
  getActiveOrganizationId,
  setStoredActiveOrganizationId,
} from "@edenscale/shared/active-org"
import type { components } from "@edenscale/api/schema"

// TODO: tests pending frontend test harness setup

type MembershipRead = components["schemas"]["MembershipRead"]
type UserRole = components["schemas"]["UserRole"]

export interface ActiveOrganizationContextValue {
  memberships: MembershipRead[]
  activeMembership: MembershipRead | null
  activeOrganizationId: string | null
  setActiveOrganizationId: (id: string | null) => void
  isSuperadmin: boolean
  isLoading: boolean
  appRoles: readonly UserRole[] | null
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
  const queryClient = useQueryClient()
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const membershipsQuery = useApiQuery("/users/me/memberships", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const [activeOrganizationId, setActiveOrganizationIdState] = useState<
    string | null
  >(() => getActiveOrganizationId())

  const memberships = useMemo<MembershipRead[]>(() => {
    const all = membershipsQuery.data ?? []
    return roles ? all.filter((m) => roles.includes(m.role)) : all
  }, [membershipsQuery.data, roles])
  const isSuperadmin = meQuery.data?.is_superadmin === true

  // No auto-heal effect here by design: once inside a scoped app URL, the URL
  // (resolved by OrgScopeLayout) is the source of truth for which org is
  // active, not this stored id. Falling back to memberships[0] here would
  // race OrgScopeLayout's own resolution and could stomp the URL's choice.
  // The localStorage-seeded initial state above is only a pre-mount guess.

  const setActiveOrganizationId = useCallback(
    (id: string | null) => {
      const changed = id !== activeOrganizationId
      setActiveOrganizationIdState(id)
      setStoredActiveOrganizationId(id)
      if (changed) {
        queryClient.invalidateQueries()
      }
    },
    [activeOrganizationId, queryClient],
  )

  const activeMembership = useMemo<MembershipRead | null>(
    () =>
      memberships.find((m) => m.organization_id === activeOrganizationId) ??
      null,
    [memberships, activeOrganizationId],
  )

  const value = useMemo<ActiveOrganizationContextValue>(
    () => ({
      memberships,
      activeMembership,
      activeOrganizationId,
      setActiveOrganizationId,
      isSuperadmin,
      isLoading: meQuery.isLoading || membershipsQuery.isLoading,
      appRoles: roles ?? null,
    }),
    [
      memberships,
      activeMembership,
      activeOrganizationId,
      setActiveOrganizationId,
      isSuperadmin,
      meQuery.isLoading,
      membershipsQuery.isLoading,
      roles,
    ],
  )

  return (
    <ActiveOrganizationContext.Provider value={value}>
      {children}
    </ActiveOrganizationContext.Provider>
  )
}
