import type { components } from "@edenscale/api/schema"

import { investorTypeLabel } from "./investorTypes"

type InvestorListItem = components["schemas"]["InvestorListItem"]

export type SortKey =
  | "name"
  | "investor_code"
  | "investor_type"
  | "primary_contact"
  | "fund_count"
  | "total_committed"
export type SortDir = "asc" | "desc"

export interface SortState {
  key: SortKey
  dir: SortDir
}

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

/** Display label for an investor's primary contact, or null when unassigned. */
export function primaryContactName(investor: InvestorListItem): string | null {
  const contact = investor.primary_contact
  if (!contact) return null
  const name = `${contact.first_name} ${contact.last_name}`.trim()
  return name || null
}

/** Comparator for the investor register.
 *
 * Two deliberate rules: investors with a missing value (no type, no assigned
 * contact) always sort last regardless of direction, so the em-dash rows never
 * break up the populated ones; and name is the tiebreaker on every key, so
 * equal values keep a stable, predictable order instead of depending on the
 * order the API happened to return.
 */
export function compareInvestors(
  a: InvestorListItem,
  b: InvestorListItem,
  { key, dir }: SortState,
): number {
  const sign = dir === "asc" ? 1 : -1
  const byName = () => a.name.localeCompare(b.name)

  switch (key) {
    case "fund_count":
      return (a.fund_count - b.fund_count) * sign || byName()
    case "total_committed":
      return (
        (parseDecimal(a.total_committed) - parseDecimal(b.total_committed)) *
          sign || byName()
      )
    case "investor_code":
      return compareNullableText(a.investor_code, b.investor_code, sign, byName)
    case "investor_type":
      // Compare the labels, not the raw enum values, so the order matches what
      // the column actually shows.
      return compareNullableText(
        investorTypeLabel(a.investor_type),
        investorTypeLabel(b.investor_type),
        sign,
        byName,
      )
    case "primary_contact":
      return compareNullableText(
        primaryContactName(a),
        primaryContactName(b),
        sign,
        byName,
      )
    case "name":
    default:
      return byName() * sign
  }
}

/** Empty values sort last in both directions — the `return 1` / `return -1`
 *  deliberately sidestep the direction sign. */
function compareNullableText(
  left: string | null | undefined,
  right: string | null | undefined,
  sign: number,
  byName: () => number,
) {
  if (!left && !right) return byName()
  if (!left) return 1
  if (!right) return -1
  return left.localeCompare(right) * sign || byName()
}

export function sortInvestors(
  investors: readonly InvestorListItem[],
  sort: SortState,
): InvestorListItem[] {
  return [...investors].sort((a, b) => compareInvestors(a, b, sort))
}

/** Re-selecting the active column flips direction. A new column starts
 *  ascending, except the numeric ones where "most first" is what you want. */
export function nextSortState(current: SortState, key: SortKey): SortState {
  if (current.key === key) {
    return { key, dir: current.dir === "asc" ? "desc" : "asc" }
  }
  return {
    key,
    dir: key === "fund_count" || key === "total_committed" ? "desc" : "asc",
  }
}
