import { useCallback, useMemo } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { authClient, getSessionToken, SESSION_QUERY_KEY } from "@/lib/neonAuth"

interface User {
  id: string
  email: string
  username?: string | null
}

/**
 * Reactive auth state backed by Neon Auth.
 *
 * The session is read via TanStack Query so every consumer stays in sync; the
 * `<NeonAuthUIProvider>` `onSessionChange` callback (see `main.tsx`)
 * invalidates this query on sign-in / sign-out so the UI updates immediately.
 */
export function useAuth() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async () => {
      const { data } = await authClient.getSession()
      return data ?? null
    },
    staleTime: 30 * 1000,
  })

  const sessionUser = data?.user ?? null
  const user: User | null = sessionUser
    ? {
        id: String(sessionUser.id),
        email: sessionUser.email ?? "",
        username: sessionUser.name ?? sessionUser.email ?? "",
      }
    : null

  const isAuthenticated = !!user

  const logout = useCallback(async () => {
    await authClient.signOut()
    queryClient.setQueryData(SESSION_QUERY_KEY, null)
    await queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY })
  }, [queryClient])

  const getToken = useCallback((): Promise<string | null> => getSessionToken(), [])

  return useMemo(
    () => ({ user, isLoading, isAuthenticated, logout, getToken }),
    [user, isLoading, isAuthenticated, logout, getToken],
  )
}
