import type { components } from "@edenscale/api/schema"

export type InvestorType = components["schemas"]["InvestorType"]

/** Display labels for the investor_type enum, in the order they appear in the
 *  select. Ordered by how often a private fund actually sees them, with the
 *  catch-all last, rather than alphabetically. */
export const INVESTOR_TYPE_OPTIONS: Array<{
  value: InvestorType
  label: string
}> = [
  { value: "individual", label: "Individual" },
  { value: "family_office", label: "Family office" },
  { value: "trust", label: "Trust" },
  { value: "endowment", label: "Endowment" },
  { value: "foundation", label: "Foundation" },
  { value: "pension", label: "Pension" },
  { value: "insurance", label: "Insurance" },
  { value: "sovereign_wealth_fund", label: "Sovereign wealth fund" },
  { value: "fund_of_funds", label: "Fund of funds" },
  { value: "asset_manager", label: "Asset manager" },
  { value: "bank", label: "Bank" },
  { value: "corporate", label: "Corporate" },
  { value: "other", label: "Other" },
]

const LABELS = new Map(
  INVESTOR_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

/** Label for a stored investor type, or null when unset. Falls back to the raw
 *  value so a member added to the API before this map is updated still renders
 *  as something rather than vanishing. */
export function investorTypeLabel(
  value: string | null | undefined,
): string | null {
  if (!value) return null
  return LABELS.get(value as InvestorType) ?? value
}
