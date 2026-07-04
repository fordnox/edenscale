import { describe, expect, it } from "vitest"

import {
  FUND_SECTIONS,
  fundSectionPath,
  fundSlugFromPath,
  fundPath,
  orgPath,
} from "./managerRoutes"

describe("fundSlugFromPath", () => {
  it("returns the fund slug for a fund page", () => {
    expect(fundSlugFromPath("/manager/acme/fund-a")).toBe("fund-a")
  })

  it("returns the fund slug for fund section pages", () => {
    for (const section of FUND_SECTIONS) {
      expect(fundSlugFromPath(fundSectionPath("acme", "fund-a", section))).toBe(
        "fund-a",
      )
    }
  })

  it("accepts trailing slashes", () => {
    expect(fundSlugFromPath("/manager/acme/fund-a/")).toBe("fund-a")
  })

  it("returns undefined for static org child routes", () => {
    for (const segment of [
      "funds",
      "investors",
      "calls",
      "distributions",
      "documents",
      "letters",
      "tasks",
      "notifications",
      "settings",
      "audit-log",
    ]) {
      expect(fundSlugFromPath(`/manager/acme/${segment}`)).toBeUndefined()
    }
  })

  it("returns undefined for top-level and org routes", () => {
    expect(fundSlugFromPath("/manager")).toBeUndefined()
    expect(fundSlugFromPath("/manager/acme")).toBeUndefined()
    expect(fundSlugFromPath("/manager/profile")).toBeUndefined()
  })

  it("returns undefined for reserved second segments", () => {
    expect(
      fundSlugFromPath("/manager/superadmin/organizations"),
    ).toBeUndefined()
    expect(fundSlugFromPath("/manager/invitations/accept")).toBeUndefined()
  })

  it("returns undefined outside the manager mount", () => {
    expect(fundSlugFromPath("/app/acme/fund-a")).toBeUndefined()
    expect(fundSlugFromPath("/investor/acme/fund-a")).toBeUndefined()
  })

  it("round-trips paths built by the helpers", () => {
    expect(fundSlugFromPath(fundPath("acme", "fund-a"))).toBe("fund-a")
    expect(fundSlugFromPath(orgPath("acme", "funds"))).toBeUndefined()
    expect(fundSlugFromPath(orgPath("acme"))).toBeUndefined()
  })
})
