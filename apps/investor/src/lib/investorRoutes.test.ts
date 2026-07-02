import { describe, expect, it } from "vitest"

import { fundSlugFromPath, fundPath, orgPath } from "./investorRoutes"

describe("fundSlugFromPath", () => {
  it("returns the fund slug for a fund page", () => {
    expect(fundSlugFromPath("/investor/acme/fund-a")).toBe("fund-a")
  })

  it("accepts trailing slashes", () => {
    expect(fundSlugFromPath("/investor/acme/fund-a/")).toBe("fund-a")
  })

  it("returns undefined for static org child routes", () => {
    for (const segment of [
      "funds",
      "calls",
      "distributions",
      "documents",
      "letters",
      "notifications",
    ]) {
      expect(fundSlugFromPath(`/investor/acme/${segment}`)).toBeUndefined()
    }
  })

  it("returns undefined for top-level and org routes", () => {
    expect(fundSlugFromPath("/investor")).toBeUndefined()
    expect(fundSlugFromPath("/investor/acme")).toBeUndefined()
    expect(fundSlugFromPath("/investor/profile")).toBeUndefined()
  })

  it("returns undefined for reserved second segments", () => {
    expect(fundSlugFromPath("/investor/invitations/accept")).toBeUndefined()
  })

  it("returns undefined outside the investor mount", () => {
    expect(fundSlugFromPath("/app/acme/fund-a")).toBeUndefined()
    expect(fundSlugFromPath("/manager/acme/fund-a")).toBeUndefined()
  })

  it("round-trips paths built by the helpers", () => {
    expect(fundSlugFromPath(fundPath("acme", "fund-a"))).toBe("fund-a")
    expect(fundSlugFromPath(orgPath("acme", "funds"))).toBeUndefined()
    expect(fundSlugFromPath(orgPath("acme"))).toBeUndefined()
  })
})
