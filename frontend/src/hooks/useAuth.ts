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
      if (hanko.session.isValid()) {
        const hankoUser = await hanko.user.getCurrent()
        setUser({
          id: hankoUser.id,
          email: hankoUser.email,
          username: hankoUser.email,
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
    await hanko.user.logout()
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
