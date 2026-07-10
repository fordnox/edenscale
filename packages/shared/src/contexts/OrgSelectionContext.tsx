import { createContext, useCallback, useContext, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import {
  getActiveOrganizationId,
  setStoredActiveOrganizationId,
} from "@edenscale/shared/active-org"
import type { components } from "@edenscale/api/schema"

type UserRole = components["schemas"]["UserRole"]

// The app-agnostic slice of org context: which org is active plus which
// invitation roles this app surfaces. Shared components (the pending-
// invitations banner/dialog) depend only on this, so the manager apps'
// membership provider and the investor app's organizations provider can
// diverge freely above it.
export interface OrgSelectionContextValue {
  activeOrganizationId: string | null
  setActiveOrganizationId: (id: string | null) => void
  // Invitation roles this app surfaces (see usePendingInvitations); null
  // means all.
  appRoles: readonly UserRole[] | null
  isLoading: boolean
}

export const OrgSelectionContext =
  createContext<OrgSelectionContextValue | null>(null)

export function useOrgSelection(): OrgSelectionContextValue {
  const ctx = useContext(OrgSelectionContext)
  if (!ctx) {
    throw new Error(
      "useOrgSelection must be used within an organization provider",
    )
  }
  return ctx
}

// Active-org id state shared by both providers: localStorage-seeded,
// persisted on change, and a full query invalidation when the org actually
// switches (every org-scoped query keys off the X-Organization-Id header,
// not the query key).
//
// No auto-heal effect here by design: once inside a scoped app URL, the URL
// (resolved by OrgScopeLayout / OrgLayout) is the source of truth for which
// org is active, not this stored id. Falling back to the first org here
// would race the layout's own resolution and could stomp the URL's choice.
// The localStorage-seeded initial state is only a pre-mount guess.
export function useActiveOrganizationIdState(): [
  string | null,
  (id: string | null) => void,
] {
  const queryClient = useQueryClient()
  const [activeOrganizationId, setActiveOrganizationIdState] = useState<
    string | null
  >(() => getActiveOrganizationId())

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

  return [activeOrganizationId, setActiveOrganizationId]
}
