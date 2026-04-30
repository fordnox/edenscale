import { useCallback } from "react"
import { useSearchParams } from "react-router-dom"

export function useTabParam<T extends string>(
  validTabs: readonly T[],
  defaultTab: T,
  paramName = "tab",
): [T, (tab: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(paramName)
  const current = (validTabs as readonly string[]).includes(raw ?? "")
    ? (raw as T)
    : defaultTab

  const setTab = useCallback(
    (tab: T) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (tab === defaultTab) {
            next.delete(paramName)
          } else {
            next.set(paramName, tab)
          }
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams, defaultTab, paramName],
  )

  return [current, setTab]
}
