import { useContext } from "react"

import {
  ActiveOrganizationContext,
  type ActiveOrganizationContextValue,
} from "@edenscale/shared/contexts/ActiveOrganizationContext"

export function useActiveOrganization(): ActiveOrganizationContextValue {
  const ctx = useContext(ActiveOrganizationContext)
  if (!ctx) {
    throw new Error(
      "useActiveOrganization must be used within an ActiveOrganizationProvider",
    )
  }
  return ctx
}
