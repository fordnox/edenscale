import { useContext } from "react"

import {
  InvestorOrganizationsContext,
  type InvestorOrganizationsContextValue,
} from "@/contexts/InvestorOrganizationsContext"

export function useInvestorOrganizations(): InvestorOrganizationsContextValue {
  const ctx = useContext(InvestorOrganizationsContext)
  if (!ctx) {
    throw new Error(
      "useInvestorOrganizations must be used within an InvestorOrganizationsProvider",
    )
  }
  return ctx
}
