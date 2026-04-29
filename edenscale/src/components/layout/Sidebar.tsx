import {
  LayoutDashboard,
  Layers,
  Users,
  ArrowDownToLine,
  ArrowUpFromLine,
  FileText,
  Mail,
  ClipboardCheck,
  Bell,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { Route } from "@/lib/router"
import { firm, currentUser } from "@/data/mock"

const items: Array<{ id: Route; label: string; icon: typeof LayoutDashboard }> = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "funds", label: "Funds", icon: Layers },
  { id: "investors", label: "Investors", icon: Users },
  { id: "calls", label: "Capital Calls", icon: ArrowDownToLine },
  { id: "distributions", label: "Distributions", icon: ArrowUpFromLine },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "letters", label: "Letters", icon: Mail },
  { id: "tasks", label: "Tasks", icon: ClipboardCheck },
  { id: "notifications", label: "Notifications", icon: Bell },
]

export function Sidebar({
  current,
  onNavigate,
}: {
  current: Route
  onNavigate: (route: Route) => void
}) {
  return (
    <aside className="sticky top-0 hidden h-svh w-[260px] shrink-0 flex-col border-r border-[color:var(--border-hairline)] bg-page md:flex">
      <div className="flex items-center gap-3 px-6 pt-7 pb-6">
        <span className="inline-flex size-7 items-center justify-center text-conifer-700">
          <svg viewBox="0 0 64 64" className="size-7" aria-hidden="true">
            <path
              fill="currentColor"
              fillRule="evenodd"
              clipRule="evenodd"
              d="M32 4 C 18 12, 10 24, 10 36 C 10 49, 20 60, 32 60 C 44 60, 54 49, 54 36 C 54 24, 46 12, 32 4 Z M32 50 L 32 30 L 26 30 L 32 22 L 38 30 L 32 30 L 32 50 Z"
            />
          </svg>
        </span>
        <div className="flex flex-col leading-tight">
          <span className="font-sans text-[16px] font-semibold tracking-[-0.04em] text-ink-900">
            {firm.name}
          </span>
          <span className="font-sans text-[11px] tracking-[0.04em] text-ink-500">
            LP portal · Manager view
          </span>
        </div>
      </div>

      <hr className="es-rule mx-6" />

      <nav className="flex-1 px-3 py-5">
        <ul className="flex flex-col gap-0.5">
          {items.map(({ id, label, icon: Icon }) => {
            const active = current === id
            return (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => onNavigate(id)}
                  className={cn(
                    "group flex w-full items-center gap-3 rounded-xs px-3 py-2.5 text-left",
                    "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                    "font-sans text-[14px]",
                    active
                      ? "bg-parchment-200 text-ink-900 font-medium"
                      : "text-ink-700 hover:bg-parchment-100 hover:text-ink-900",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon
                    className={cn(
                      "size-[18px] shrink-0",
                      active ? "text-conifer-700" : "text-ink-500",
                    )}
                    strokeWidth={1.5}
                  />
                  <span>{label}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      <hr className="es-rule mx-6" />

      <div className="flex items-center gap-3 px-6 py-5">
        <span className="inline-flex size-9 items-center justify-center bg-conifer-700 text-parchment-50 font-display text-base font-medium">
          {currentUser.first_name.charAt(0)}
          {currentUser.last_name.charAt(0)}
        </span>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate font-sans text-[13px] font-medium text-ink-900">
            {currentUser.first_name} {currentUser.last_name}
          </span>
          <span className="truncate font-sans text-[11px] text-ink-500">
            {currentUser.title}
          </span>
        </div>
      </div>
    </aside>
  )
}
