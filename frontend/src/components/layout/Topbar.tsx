import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { ChevronDown, Menu, Search } from "lucide-react"

import { cn } from "@/lib/utils"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { Kbd } from "@/components/ui/kbd"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { components } from "@/lib/schema"

type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Record<UserRole, string> = {
  superadmin: "Superadmin",
  admin: "Admin",
  fund_manager: "Fund manager",
  lp: "LP",
}

interface TopbarProps {
  onOpenSidebar: () => void
  onOpenSearch: () => void
}

export function Topbar({ onOpenSidebar, onOpenSearch }: TopbarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
      <div className="flex items-center gap-4 px-4 py-3 md:gap-6 md:px-8 md:py-4">
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
          onClick={onOpenSearch}
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

        <div className="ml-auto flex items-center">
          <OrganizationSwitcher />
        </div>
      </div>
    </header>
  )
}

function OrganizationSwitcher() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const {
    memberships,
    activeMembership,
    setActiveOrganizationId,
    isSuperadmin,
  } = useActiveOrganization()

  if (memberships.length === 0 && !isSuperadmin) {
    return null
  }

  const triggerLabel =
    activeMembership?.organization.name ??
    (isSuperadmin ? "All organizations" : "—")

  const handleSelect = (organizationId: number) => {
    if (organizationId === activeMembership?.organization_id) return
    setActiveOrganizationId(organizationId)
    queryClient.invalidateQueries()
  }

  const handleViewAll = () => {
    navigate("/superadmin/organizations")
  }

  if (memberships.length === 1 && !isSuperadmin) {
    return (
      <span
        className={cn(
          "inline-flex h-9 max-w-[200px] items-center rounded-xs border border-transparent px-3",
          "font-sans text-[13px] font-medium text-ink-900",
        )}
        title={triggerLabel}
      >
        <span className="truncate">{triggerLabel}</span>
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
                  onSelect={() => handleSelect(m.organization_id)}
                  className={cn(
                    "min-h-11 md:min-h-0 gap-3",
                    isActive && "bg-parchment-200",
                  )}
                >
                  <span className="flex-1 min-w-0 truncate font-sans text-[13px] text-ink-900">
                    {m.organization.name}
                  </span>
                  <span className="shrink-0 font-sans text-[10px] tracking-[0.06em] uppercase text-ink-500">
                    {ROLE_LABELS[m.role]}
                  </span>
                </DropdownMenuItem>
              )
            })}
          </>
        )}
        {isSuperadmin && (
          <>
            {memberships.length > 0 && <DropdownMenuSeparator />}
            <DropdownMenuItem
              onSelect={handleViewAll}
              className="min-h-11 md:min-h-0 font-sans text-[13px] text-ink-900"
            >
              <span>View all organizations →</span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
