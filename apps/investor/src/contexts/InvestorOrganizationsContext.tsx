import { createContext, useMemo, type ReactNode } from "react"

import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import {
  OrgSelectionContext,
  useActiveOrganizationIdState,
  type OrgSelectionContextValue,
} from "@edenscale/shared/contexts/OrgSelectionContext"
import type { components } from "@edenscale/api/schema"

type InvestorOrganizationRead =
  components["schemas"]["InvestorOrganizationRead"]

// Investor-portal org context: organizations come from /investor/organizations
// — the orgs where this user is a linked contact of an investor. There are no
// memberships or roles here; a fund admin who personally invested appears via
// their links exactly like any other investor.
export interface InvestorOrganizationsContextValue {
  organizations: InvestorOrganizationRead[]
  activeOrganization: InvestorOrganizationRead | null
  activeOrganizationId: string | null
  setActiveOrganizationId: (id: string | null) => void
  isLoading: boolean
}

export const InvestorOrganizationsContext =
  createContext<InvestorOrganizationsContextValue | null>(null)

// Which pending invitations the investor app surfaces (see
// usePendingInvitations); investor invitations carry the lp role.
const INVITATION_ROLES = ["lp"] as const

export function InvestorOrganizationsProvider({
  children,
}: {
  children: ReactNode
}) {
  const organizationsQuery = useApiQuery("/investor/organizations", undefined, {
    staleTime: 5 * 60 * 1000,
  })

  const [activeOrganizationId, setActiveOrganizationId] =
    useActiveOrganizationIdState()

  const organizations = useMemo(
    () => organizationsQuery.data ?? [],
    [organizationsQuery.data],
  )

  const activeOrganization = useMemo(
    () =>
      organizations.find(
        (org) => org.organization_id === activeOrganizationId,
      ) ?? null,
    [organizations, activeOrganizationId],
  )

  const isLoading = organizationsQuery.isLoading

  const value = useMemo<InvestorOrganizationsContextValue>(
    () => ({
      organizations,
      activeOrganization,
      activeOrganizationId,
      setActiveOrganizationId,
      isLoading,
    }),
    [
      organizations,
      activeOrganization,
      activeOrganizationId,
      setActiveOrganizationId,
      isLoading,
    ],
  )

  const selectionValue = useMemo<OrgSelectionContextValue>(
    () => ({
      activeOrganizationId,
      setActiveOrganizationId,
      appRoles: INVITATION_ROLES,
      isLoading,
    }),
    [activeOrganizationId, setActiveOrganizationId, isLoading],
  )

  return (
    <OrgSelectionContext.Provider value={selectionValue}>
      <InvestorOrganizationsContext.Provider value={value}>
        {children}
      </InvestorOrganizationsContext.Provider>
    </OrgSelectionContext.Provider>
  )
}
