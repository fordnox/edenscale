import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import type { components } from "@/lib/schema"

type MembershipRead = components["schemas"]["MembershipRead"]

export function useActiveMembership(): MembershipRead | null {
  const { activeMembership } = useActiveOrganization()
  return activeMembership
}
