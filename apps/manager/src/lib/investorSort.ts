import type { components } from "@edenscale/api/schema"

type InvestorListItem = components["schemas"]["InvestorListItem"]

export type SortKey = "name" | "investor_type" | "fund_count" | "total_committed"
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

/** Comparator for the investor register.
 *
 * Two deliberate rules: investors with no type always sort last regardless of
 * direction, so the em-dash rows never break up the typed ones; and name is the
 * tiebreaker on every key, so equal values keep a stable, predictable order
 * instead of depending on the order the API happened to return.
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
    case "investor_type": {
      const left = a.investor_type
      const right = b.investor_type
      if (!left && !right) return byName()
      if (!left) return 1
      if (!right) return -1
      return left.localeCompare(right) * sign || byName()
    }
    case "name":
    default:
      return byName() * sign
  }
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
