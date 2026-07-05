import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useEffect,
  type ReactNode,
} from "react"
import { hanko, getSessionToken } from "@edenscale/auth/hanko"

interface User {
  id: string
  email: string
  username?: string | null
}

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  logout: () => Promise<void>
  getToken: () => string | null
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
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

  const value = useMemo(
    () => ({ user, isLoading, isAuthenticated, logout, getToken }),
    [user, isLoading, isAuthenticated, logout, getToken],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>")
  }
  return ctx
}
