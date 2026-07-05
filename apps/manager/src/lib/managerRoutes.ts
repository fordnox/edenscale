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
  "funds",
  "investors",
  "calls",
  "distributions",
  "documents",
  "letters",
  "tasks",
  "notifications",
  "audit-log",
])

// Static child routes declared under /manager/:orgSlug in App.tsx. A third path
// segment that isn't one of these is a fund slug (the dynamic :fundSlug
// route). Kept here so nav/routing can tell a fund slug apart from a static
// page without depending on route-match internals.
export const STATIC_ORG_CHILD_SEGMENTS = new Set([
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
])

/** The fund slug for a /manager/:orgSlug/:fundSlug path, or undefined if the
 * path is a top-level or static org route rather than a fund page. */
export function fundSlugFromPath(pathname: string): string | undefined {
  const parts = pathname.replace(/^\/+|\/+$/g, "").split("/")
  if (parts.length < 3 || parts[0] !== "manager") return undefined
  const [, orgSlug, segment] = parts
  if (RESERVED_ORG_SLUGS.has(orgSlug)) return undefined
  if (STATIC_ORG_CHILD_SEGMENTS.has(segment)) return undefined
  return segment
}

// Child routes declared under /manager/:orgSlug/:fundSlug in App.tsx. The fund
// overview is the index route and has no segment of its own.
export const FUND_SECTIONS = [
  "commitments",
  "calls",
  "distributions",
  "team",
  "letters",
  "settings",
] as const

export type FundSection = (typeof FUND_SECTIONS)[number]

export function orgPath(orgSlug: string, subpath = ""): string {
  const trimmed = subpath.replace(/^\/+/, "")
  return trimmed ? `/manager/${orgSlug}/${trimmed}` : `/manager/${orgSlug}`
}

export function fundPath(orgSlug: string, fundSlug: string): string {
  return `/manager/${orgSlug}/${fundSlug}`
}

export function fundSectionPath(
  orgSlug: string,
  fundSlug: string,
  section: FundSection,
): string {
  return `${fundPath(orgSlug, fundSlug)}/${section}`
}
