const STORAGE_KEY = "newtaven.active_org_id"

export function getActiveOrganizationId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setStoredActiveOrganizationId(id: string | null): void {
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
