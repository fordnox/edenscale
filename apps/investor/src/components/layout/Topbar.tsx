import { useNavigate } from "react-router-dom"
import { ChevronDown, Menu } from "lucide-react"

import { cn } from "@edenscale/shared/utils"
import { orgPath } from "@/lib/investorRoutes"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
import type { components } from "@edenscale/api/schema"

type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Partial<Record<UserRole, string>> = {
  admin: "Admin",
  fund_manager: "Fund manager",
  lp: "LP",
}

interface TopbarProps {
  onOpenSidebar: () => void
}

export function Topbar({ onOpenSidebar }: TopbarProps) {
  return (
    <header className="sticky top-0 z-20 flex items-center border-b border-[color:var(--border-hairline)] bg-page/85 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-page/75 md:hidden">
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label="Open navigation"
        className={cn(
          "inline-flex size-11 items-center justify-center rounded-xs",
          "text-ink-700 transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
          "hover:bg-parchment-200 hover:text-ink-900",
          "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
        )}
      >
        <Menu strokeWidth={1.5} className="size-5" />
      </button>
    </header>
  )
}

export function OrganizationSwitcher() {
  const navigate = useNavigate()
  const { memberships, activeMembership } = useActiveOrganization()

  if (memberships.length === 0) {
    return null
  }

  const triggerLabel =
    activeMembership?.organization.name ??
    (memberships.length > 1 ? "All organizations" : "—")

  // Only navigate here — OrgScopeLayout is the single place that calls
  // setActiveOrganizationId, triggered by the resulting route change.
  const handleSelect = (orgSlug: string) => {
    navigate(orgPath(orgSlug))
  }

  if (memberships.length === 1) {
    const membership = activeMembership ?? memberships[0]
    return (
      <span
        title={triggerLabel}
        className="inline-flex max-w-[200px] flex-col justify-center gap-0.5 rounded-xs border border-transparent px-3 py-1.5"
      >
        <span className="truncate font-sans text-[13px] font-medium text-ink-900">
          {triggerLabel}
        </span>
        <span className="truncate font-sans text-[11px] tracking-[0.04em] text-ink-500">
          {ROLE_LABELS[membership.role]}
        </span>
      </span>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "inline-flex h-9 max-w-[200px] items-center gap-2 rounded-xs border border-[color:var(--border-hairline)] bg-surface px-3",
          "font-sans text-[13px] font-medium text-ink-900",
          "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
          "hover:border-conifer-600",
          "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
        )}
        aria-label="Switch organization"
      >
        <span className="truncate">{triggerLabel}</span>
        <ChevronDown
          strokeWidth={1.5}
          className="size-4 shrink-0 text-ink-500"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {memberships.length > 0 && (
          <>
            <DropdownMenuLabel className="text-[11px] tracking-[0.06em] text-ink-500 uppercase font-medium">
              Organizations
            </DropdownMenuLabel>
            {memberships.map((m) => {
              const isActive = m.organization_id === activeMembership?.organization_id
              return (
                <DropdownMenuItem
                  key={m.id}
                  onSelect={() => handleSelect(m.organization.slug)}
                  className={cn(
                    "min-h-11 md:min-h-0 gap-3",
                    isActive && "bg-parchment-200",
                  )}
                >
                  <span className="flex-1 min-w-0 truncate font-sans text-[13px] text-ink-900">
                    {m.organization.name}
                  </span>
                  <span className="shrink-0 font-sans text-[10px] tracking-[0.06em] uppercase text-ink-500">
                    {ROLE_LABELS[m.role] ?? "Member"}
                  </span>
                </DropdownMenuItem>
              )
            })}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
