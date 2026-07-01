// Mirrors app/core/slugs.py's RESERVED_SLUGS on the backend — keep in sync.
export const RESERVED_ORG_SLUGS = new Set([
  "app",
  "login",
  "profile",
  "onboarding",
  "settings",
  "superadmin",
  "invitations",
  "api",
])

export type FundDetailTab =
  | "commitments"
  | "calls"
  | "distributions"
  | "team"
  | "letters"

export function orgPath(orgSlug: string, subpath = ""): string {
  const trimmed = subpath.replace(/^\/+/, "")
  return trimmed ? `/app/${orgSlug}/${trimmed}` : `/app/${orgSlug}`
}

export function fundPath(orgSlug: string, fundSlug: string): string {
  return `/app/${orgSlug}/${fundSlug}`
}

export function fundTabPath(
  orgSlug: string,
  fundSlug: string,
  tab: FundDetailTab,
): string {
  return `${fundPath(orgSlug, fundSlug)}?tab=${tab}`
}
