// Mirrors the active organization id, read synchronously by lib/api.ts's
// fetch middleware for the X-Organization-Id header. Updated every time
// setActiveOrganizationId fires — this is a cache, not the source of truth
// (the URL is, while inside /manager/:orgSlug or /investor/:orgSlug).
const ACTIVE_ORG_ID_KEY = "newtaven.active_org_id"

// Remembers which org the user last visited, purely to pick a redirect
// target from the bare app landing route. Distinct from the key above:
// this is a slug (URL-shaped), updated less often, and never read by the
// fetch middleware.
const LAST_VISITED_ORG_SLUG_KEY = "newtaven.last_org_slug"

export function getActiveOrganizationId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_ORG_ID_KEY)
  } catch {
    return null
  }
}

export function setStoredActiveOrganizationId(id: string | null): void {
  try {
    if (id === null) {
      localStorage.removeItem(ACTIVE_ORG_ID_KEY)
    } else {
      localStorage.setItem(ACTIVE_ORG_ID_KEY, String(id))
    }
  } catch {
    /* localStorage unavailable */
  }
}

export function getLastVisitedOrgSlug(): string | null {
  try {
    return localStorage.getItem(LAST_VISITED_ORG_SLUG_KEY)
  } catch {
    return null
  }
}

export function setLastVisitedOrgSlug(slug: string | null): void {
  try {
    if (slug === null) {
      localStorage.removeItem(LAST_VISITED_ORG_SLUG_KEY)
    } else {
      localStorage.setItem(LAST_VISITED_ORG_SLUG_KEY, slug)
    }
  } catch {
    /* localStorage unavailable */
  }
}
