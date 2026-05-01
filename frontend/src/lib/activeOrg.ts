const STORAGE_KEY = "edenscale.active_org_id"

export function getActiveOrganizationId(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function setStoredActiveOrganizationId(id: number | null): void {
  try {
    if (id === null) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, String(id))
    }
  } catch {
    /* localStorage unavailable */
  }
}
