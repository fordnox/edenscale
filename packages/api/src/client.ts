import createClient, { Middleware } from "openapi-fetch"
import type { paths } from "@edenscale/api/schema"
import { toast } from "sonner"

const ACTIVE_ORG_ID_KEY = "newtaven.active_org_id"

let unauthorizedOrganizationFallbackPath = "/"

// Injected by the host app so this package doesn't need to depend on
// @edenscale/auth (which itself depends on @edenscale/api — a hard import here
// would create a package cycle that breaks the turbo build graph).
let sessionTokenProvider: () => string | null = () => null

export function configureApiClient(options: {
  unauthorizedOrganizationFallbackPath?: string
  getSessionToken?: () => string | null
}): void {
  unauthorizedOrganizationFallbackPath =
    options.unauthorizedOrganizationFallbackPath ?? "/"
  if (options.getSessionToken) {
    sessionTokenProvider = options.getSessionToken
  }
}

function getActiveOrganizationId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_ORG_ID_KEY)
  } catch {
    return null
  }
}

const myMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = sessionTokenProvider()
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`)
    }
    const activeOrgId = getActiveOrganizationId()
    if (activeOrgId !== null) {
      request.headers.set("X-Organization-Id", String(activeOrgId))
    }
    return request
  },
  async onResponse({ response }) {
    if (!response.ok && response.status !== 401) {
      const errorData = await response.clone().json().catch(() => null)
      const message =
        errorData?.detail || errorData?.message || `Error ${response.status}: ${response.statusText}`

      if (
        response.status === 403 &&
        errorData?.detail === "Not a member of this organization" &&
        window.location.pathname !== unauthorizedOrganizationFallbackPath
      ) {
        window.location.href = unauthorizedOrganizationFallbackPath
        return response
      }

      console.error(message)
    }

    return response
  },
  async onError({ error }) {
    console.error("Network error:", error)
    const message = error instanceof Error ? error.message : "Network error occurred"
    console.error("Connection failed:", message)
    return undefined
  },
}

// The API is always served from the `api.` subdomain of whatever host the app
// is loaded from (e.g. newtaven.com -> https://api.newtaven.com), so there is no
// build-time config. Local dev is the only exception: the API runs on a
// separate port, so a VITE_API_URL override is honored (default localhost:8000).
export function getApiBaseUrl(): string {
  const { hostname, protocol } = window.location
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return import.meta.env.VITE_API_URL || "http://localhost:8000"
  }
  return `${protocol}//api.${hostname}`
}

const client = createClient<paths>({ baseUrl: getApiBaseUrl() })
client.use(myMiddleware)

export default client
