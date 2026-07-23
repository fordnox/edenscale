import { describe, expect, it } from "vitest"

import { nextSortState, sortInvestors, type SortState } from "./investorSort"

function investor(
  name: string,
  overrides: {
    investor_type?: string | null
    fund_count?: number
    total_committed?: string
  } = {},
) {
  return {
    id: name.toLowerCase().replace(/\s+/g, "-"),
    organization_id: "org",
    investor_code: null,
    name,
    // `??` would swallow an explicit null, which is exactly the case the
    // untyped-investor tests need to set up.
    investor_type:
      "investor_type" in overrides ? overrides.investor_type! : "family_office",
    accredited: null,
    total_committed: overrides.total_committed ?? "0",
    fund_count: overrides.fund_count ?? 0,
  }
}

const names = (rows: ReturnType<typeof investor>[]) => rows.map((r) => r.name)

describe("sortInvestors", () => {
  it("sorts by name in both directions", () => {
    const rows = [investor("Novak"), investor("Alderman"), investor("Kessler")]
    expect(names(sortInvestors(rows, { key: "name", dir: "asc" }))).toEqual([
      "Alderman",
      "Kessler",
      "Novak",
    ])
    expect(names(sortInvestors(rows, { key: "name", dir: "desc" }))).toEqual([
      "Novak",
      "Kessler",
      "Alderman",
    ])
  })

  it("sorts committed numerically, not as strings", () => {
    const rows = [
      investor("Nine", { total_committed: "9000000" }),
      investor("Ten", { total_committed: "10000000" }),
    ]
    // Lexicographically "10000000" < "9000000", so a string sort would invert.
    expect(
      names(sortInvestors(rows, { key: "total_committed", dir: "desc" })),
    ).toEqual(["Ten", "Nine"])
  })

  it("sorts by fund count", () => {
    const rows = [
      investor("One", { fund_count: 1 }),
      investor("Four", { fund_count: 4 }),
      investor("Two", { fund_count: 2 }),
    ]
    expect(
      names(sortInvestors(rows, { key: "fund_count", dir: "desc" })),
    ).toEqual(["Four", "Two", "One"])
  })

  it("keeps untyped investors last in both directions", () => {
    const rows = [
      investor("Blank", { investor_type: null }),
      investor("Pension", { investor_type: "pension" }),
      investor("Endowment", { investor_type: "endowment" }),
    ]
    expect(
      names(sortInvestors(rows, { key: "investor_type", dir: "asc" })),
    ).toEqual(["Endowment", "Pension", "Blank"])
    expect(
      names(sortInvestors(rows, { key: "investor_type", dir: "desc" })),
    ).toEqual(["Pension", "Endowment", "Blank"])
  })

  it("breaks ties by name so the order is stable", () => {
    const rows = [
      investor("Zeta", { fund_count: 2 }),
      investor("Alpha", { fund_count: 2 }),
    ]
    expect(
      names(sortInvestors(rows, { key: "fund_count", dir: "desc" })),
    ).toEqual(["Alpha", "Zeta"])
    expect(
      names(sortInvestors(rows, { key: "fund_count", dir: "asc" })),
    ).toEqual(["Alpha", "Zeta"])
  })

  it("does not mutate the input array", () => {
    const rows = [investor("Novak"), investor("Alderman")]
    sortInvestors(rows, { key: "name", dir: "asc" })
    expect(names(rows)).toEqual(["Novak", "Alderman"])
  })

  it("treats a blank committed amount as zero", () => {
    const rows = [
      investor("Blank", { total_committed: "" }),
      investor("Some", { total_committed: "500" }),
    ]
    expect(
      names(sortInvestors(rows, { key: "total_committed", dir: "desc" })),
    ).toEqual(["Some", "Blank"])
  })
})

describe("nextSortState", () => {
  const nameAsc: SortState = { key: "name", dir: "asc" }

  it("flips direction when the active column is re-selected", () => {
    expect(nextSortState(nameAsc, "name")).toEqual({ key: "name", dir: "desc" })
    expect(nextSortState({ key: "name", dir: "desc" }, "name")).toEqual(nameAsc)
  })

  it("starts text columns ascending and numeric columns descending", () => {
    expect(nextSortState(nameAsc, "investor_type")).toEqual({
      key: "investor_type",
      dir: "asc",
    })
    expect(nextSortState(nameAsc, "fund_count")).toEqual({
      key: "fund_count",
      dir: "desc",
    })
    expect(nextSortState(nameAsc, "total_committed")).toEqual({
      key: "total_committed",
      dir: "desc",
    })
  })
})
