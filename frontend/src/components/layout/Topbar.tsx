import { Menu, Search } from "lucide-react"

import { cn } from "@/lib/utils"
import { Kbd } from "@/components/ui/kbd"

interface TopbarProps {
  onOpenSidebar: () => void
}

export function Topbar({ onOpenSidebar }: TopbarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
      <div className="flex items-center justify-between gap-4 px-4 py-3 md:gap-6 md:px-8 md:py-4">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open navigation"
          className={cn(
            "inline-flex size-11 items-center justify-center rounded-xs md:hidden",
            "text-ink-700 transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
            "hover:bg-parchment-200 hover:text-ink-900",
            "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
          )}
        >
          <Menu strokeWidth={1.5} className="size-5" />
        </button>

        <button
          type="button"
          onClick={() => console.log("cmdk")}
          className={cn(
            "relative hidden h-9 w-[340px] items-center gap-2 rounded-xs border border-[color:var(--border-hairline)] bg-surface pl-9 pr-2 md:flex",
            "font-sans text-[13px] text-ink-500",
            "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
            "hover:border-conifer-600",
            "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
          )}
          aria-label="Open command palette"
        >
          <Search
            strokeWidth={1.5}
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-500"
          />
          <span className="flex-1 text-left">
            Search funds, investors, documents…
          </span>
          <Kbd className="bg-parchment-200 text-ink-700">⌘K</Kbd>
        </button>
      </div>
    </header>
  )
}
