import { createAuthClient } from "@neondatabase/neon-js/auth"
import { config } from "@/lib/config"

/**
 * Neon Auth client. Built from the project's auth base URL
 * (`VITE_NEON_AUTH_URL`, e.g. https://ep-xxx.neonauth.<region>.aws.neon.tech/neondb/auth).
 * Passed to `<NeonAuthUIProvider>` in `main.tsx`, which converts this vanilla
 * client into a React client for the auth UI components.
 */
export const authClient = createAuthClient(config.VITE_NEON_AUTH_URL)

/** React Query key for the cached Neon Auth session. */
export const SESSION_QUERY_KEY = ["neon-auth-session"] as const

/**
 * Return the current session's JWT access token, or `null` when signed out.
 * The token is attached as a Bearer header to backend API requests.
 */
export async function getSessionToken(): Promise<string | null> {
  const { data } = await authClient.getSession()
  return data?.session?.token ?? null
}
