import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"
import { useNavItems } from "@/hooks/useNavItems"

function deriveInitials(email: string | null | undefined) {
  if (!email) return "ES"
  const local = email.split("@")[0] ?? ""
  const parts = local.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return (local.slice(0, 2) || "ES").toUpperCase()
}

const ROLE_TAGLINES: Record<string, string> = {
  admin: "Administrator view",
  fund_manager: "Manager view",
  lp: "Limited partner view",
}

export function Sidebar() {
  const { user } = useAuth()
  const initials = deriveInitials(user?.email)
  const { items, role } = useNavItems()
  const tagline = (role && ROLE_TAGLINES[role]) ?? "Manager view"

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
            EdenScale
          </span>
          <span className="font-sans text-[11px] tracking-[0.04em] text-ink-500">
            LP portal · {tagline}
          </span>
        </div>
      </div>

      <hr className="es-rule mx-6" />

      <nav className="flex-1 px-3 py-5">
        <ul className="flex flex-col gap-0.5">
          {items.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "group flex w-full items-center gap-3 rounded-xs px-3 py-2.5 text-left",
                    "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                    "font-sans text-[14px]",
                    isActive
                      ? "bg-parchment-200 text-ink-900 font-medium"
                      : "text-ink-700 hover:bg-parchment-100 hover:text-ink-900",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        "size-[18px] shrink-0",
                        isActive ? "text-conifer-700" : "text-ink-500",
                      )}
                      strokeWidth={1.5}
                    />
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <hr className="es-rule mx-6" />

      <div className="flex items-center gap-3 px-6 py-5">
        <span className="inline-flex size-9 items-center justify-center bg-conifer-700 text-parchment-50 font-display text-base font-medium">
          {initials}
        </span>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate font-sans text-[13px] font-medium text-ink-900">
            {user?.email ?? "Signed out"}
          </span>
          <span className="truncate font-sans text-[11px] text-ink-500">
            {tagline}
          </span>
        </div>
      </div>
    </aside>
  )
}
