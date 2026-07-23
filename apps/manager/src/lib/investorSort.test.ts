import { describe, expect, it } from "vitest"

import {
  nextSortState,
  primaryContactName,
  sortInvestors,
  type SortState,
} from "./investorSort"

function investor(
  name: string,
  overrides: {
    investor_type?: string | null
    fund_count?: number
    total_committed?: string
    contact?: { first_name: string; last_name: string } | null
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
    primary_contact: overrides.contact
      ? { id: "c", email: null, ...overrides.contact }
      : null,
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

describe("primaryContactName", () => {
  it("joins the contact name", () => {
    expect(
      primaryContactName(
        investor("Acme", { contact: { first_name: "Ada", last_name: "Byron" } }),
      ),
    ).toBe("Ada Byron")
  })

  it("returns null when no contact is assigned", () => {
    expect(primaryContactName(investor("Acme"))).toBeNull()
  })
})

describe("sortInvestors by contact", () => {
  it("sorts by contact name and keeps unassigned last both ways", () => {
    const rows = [
      investor("NoContact"),
      investor("Zed", { contact: { first_name: "Zoe", last_name: "Zhang" } }),
      investor("Ann", { contact: { first_name: "Ada", last_name: "Byron" } }),
    ]
    expect(
      names(sortInvestors(rows, { key: "primary_contact", dir: "asc" })),
    ).toEqual(["Ann", "Zed", "NoContact"])
    expect(
      names(sortInvestors(rows, { key: "primary_contact", dir: "desc" })),
    ).toEqual(["Zed", "Ann", "NoContact"])
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
    expect(nextSortState(nameAsc, "primary_contact")).toEqual({
      key: "primary_contact",
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
