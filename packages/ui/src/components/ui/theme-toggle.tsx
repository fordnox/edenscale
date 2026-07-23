"use client"

import { Monitor, Moon, Sun } from "lucide-react"

import { cn } from "@edenscale/shared/utils"
import {
  useTheme,
  type Theme,
} from "@edenscale/shared/contexts/ThemeContext"

const OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "system", label: "System", icon: Monitor },
  { value: "dark", label: "Dark", icon: Moon },
]

// A compact three-way segmented control (Light / System / Dark) intended to sit
// inside the account dropdown. It is deliberately not a DropdownMenuItem so that
// changing the theme previews instantly without closing the menu.
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cn(
        "flex items-center gap-1 rounded-xs border border-[color:var(--border-hairline)] bg-sunken p-0.5",
        className,
      )}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = theme === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              "flex flex-1 items-center justify-center rounded-xs py-1",
              "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-1",
              active
                ? "bg-surface text-ink-900 shadow-sm"
                : "text-ink-500 hover:text-ink-900",
            )}
          >
            <Icon strokeWidth={1.5} className="size-3.5" />
          </button>
        )
      })}
    </div>
  )
}
