import { useState, useCallback, useMemo, useEffect } from "react"
import { hanko, getSessionToken } from "@/lib/hanko"

interface User {
  id: string
  email: string
  username?: string | null
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = !!user

  const checkSession = useCallback(async () => {
    try {
      const session = await hanko.validateSession()
      if (session.is_valid) {
        const hankoUser = await hanko.getCurrentUser()
        const primaryEmail =
          hankoUser.emails?.find((e) => e.is_primary)?.address ??
          hankoUser.emails?.[0]?.address ??
          ""
        setUser({
          id: hankoUser.user_id,
          email: primaryEmail,
          username: hankoUser.username?.username ?? primaryEmail,
        })
      } else {
        setUser(null)
      }
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // Clean up stale localStorage keys from old auth
    localStorage.removeItem("token")
    localStorage.removeItem("user")

    checkSession()

    const unsubCreate = hanko.onSessionCreated(() => {
      checkSession()
    })

    const unsubExpire = hanko.onSessionExpired(() => {
      setUser(null)
    })

    return () => {
      unsubCreate()
      unsubExpire()
    }
  }, [checkSession])

  const logout = useCallback(async () => {
    await hanko.logout()
    setUser(null)
  }, [])

  const getToken = useCallback((): string | null => {
    return getSessionToken()
  }, [])

  return useMemo(
    () => ({ user, isLoading, isAuthenticated, logout, getToken }),
    [user, isLoading, isAuthenticated, logout, getToken],
  )
}
