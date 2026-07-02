import { useCallback, useEffect, useState } from "react"

export interface UseCommandPaletteResult {
  open: boolean
  setOpen: (next: boolean) => void
  toggle: () => void
}

export function useCommandPalette(): UseCommandPaletteResult {
  const [open, setOpen] = useState(false)

  const toggle = useCallback(() => setOpen((prev) => !prev), [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [toggle])

  return { open, setOpen, toggle }
}
