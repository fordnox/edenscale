import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

export type Theme = "light" | "dark" | "system"
export type ResolvedTheme = "light" | "dark"

// Shared across the manager and investor SPAs. In production both mount under
// the same origin (newtaven.com/manager, /investor), so this key syncs the
// preference between them; in dev they're separate ports and stay independent.
export const THEME_STORAGE_KEY = "newtaven-theme"

const DARK_QUERY = "(prefers-color-scheme: dark)"

interface ThemeContextValue {
  /** The user's choice, including "system". */
  theme: Theme
  /** The concrete theme currently applied ("system" resolved against the OS). */
  resolvedTheme: ResolvedTheme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark" || value === "system"
}

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return "system"
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (isTheme(stored)) return stored
  } catch {
    // Access to localStorage can throw (private mode, blocked cookies).
  }
  return "system"
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "light"
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light"
}

// Mirrors the inline no-flash script in each app's index.html. Keep the two in
// sync: the script paints the correct theme before React mounts, this keeps it
// correct afterwards.
function applyTheme(resolved: ResolvedTheme) {
  if (typeof document === "undefined") return
  const root = document.documentElement
  root.classList.toggle("dark", resolved === "dark")
  root.style.colorScheme = resolved
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme)
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme)

  const resolvedTheme: ResolvedTheme = theme === "system" ? systemTheme : theme

  // Follow the OS while (and only while) the user is on "system".
  useEffect(() => {
    const media = window.matchMedia(DARK_QUERY)
    const onChange = (event: MediaQueryListEvent) =>
      setSystemTheme(event.matches ? "dark" : "light")
    media.addEventListener("change", onChange)
    return () => media.removeEventListener("change", onChange)
  }, [])

  useEffect(() => {
    applyTheme(resolvedTheme)
  }, [resolvedTheme])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Non-fatal: the theme still applies for this session.
    }
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return ctx
}
