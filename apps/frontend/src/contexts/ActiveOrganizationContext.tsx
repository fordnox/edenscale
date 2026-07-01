import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useQueryClient } from "@tanstack/react-query"

import { useApiQuery } from "@/hooks/useApiQuery"
import {
  getActiveOrganizationId,
  setStoredActiveOrganizationId,
} from "@/lib/activeOrg"
import type { components } from "@/lib/schema"

// TODO: tests pending frontend test harness setup

type MembershipRead = components["schemas"]["MembershipRead"]

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
}

export function ActiveOrganizationProvider({
  children,
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

  const memberships = useMemo<MembershipRead[]>(
    () => membershipsQuery.data ?? [],
    [membershipsQuery.data],
  )
  const isSuperadmin = meQuery.data?.role === "superadmin"

  // No auto-heal effect here by design: once inside /app/:orgSlug, the URL
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
    }),
    [
      memberships,
      activeMembership,
      activeOrganizationId,
      setActiveOrganizationId,
      isSuperadmin,
      meQuery.isLoading,
      membershipsQuery.isLoading,
    ],
  )

  return (
    <ActiveOrganizationContext.Provider value={value}>
      {children}
    </ActiveOrganizationContext.Provider>
  )
}
