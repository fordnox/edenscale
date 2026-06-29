import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

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
  activeOrganizationId: number | null
  setActiveOrganizationId: (id: number | null) => void
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
  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const membershipsQuery = useApiQuery("/users/me/memberships", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const [activeOrganizationId, setActiveOrganizationIdState] = useState<
    number | null
  >(() => getActiveOrganizationId())

  const memberships = useMemo<MembershipRead[]>(
    () => membershipsQuery.data ?? [],
    [membershipsQuery.data],
  )
  const isSuperadmin = meQuery.data?.role === "superadmin"

  useEffect(() => {
    if (membershipsQuery.isLoading || !membershipsQuery.data) {
      return
    }
    if (memberships.length === 0) {
      if (activeOrganizationId !== null) {
        setActiveOrganizationIdState(null)
        setStoredActiveOrganizationId(null)
      }
      return
    }
    const matches =
      activeOrganizationId !== null &&
      memberships.some((m) => m.organization_id === activeOrganizationId)
    if (matches) return
    const fallback = memberships[0].organization_id
    setActiveOrganizationIdState(fallback)
    setStoredActiveOrganizationId(fallback)
  }, [
    activeOrganizationId,
    memberships,
    membershipsQuery.data,
    membershipsQuery.isLoading,
  ])

  const setActiveOrganizationId = useCallback((id: number | null) => {
    setActiveOrganizationIdState(id)
    setStoredActiveOrganizationId(id)
  }, [])

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
