import { useNavigate } from "react-router-dom"
import { ChevronDown } from "lucide-react"

import { cn } from "@edenscale/shared/utils"
import { orgPath } from "@/lib/investorRoutes"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
// Everyone in this portal is here as an investor (access is contact-link
// based), so the secondary label is a constant.
const ACCESS_LABEL = "Investor"

export function OrganizationSwitcher() {
  const navigate = useNavigate()
  const { organizations, activeOrganization } = useInvestorOrganizations()

  if (organizations.length === 0) {
    return null
  }

  const triggerLabel =
    activeOrganization?.organization.name ??
    (organizations.length > 1 ? "All organizations" : "—")

  // Only navigate here — OrgLayout is the single place that calls
  // setActiveOrganizationId, triggered by the resulting route change.
  const handleSelect = (orgSlug: string) => {
    navigate(orgPath(orgSlug))
  }

  // Single org: nothing to switch between, so this stays a plain label. The
  // brand mark beside it is the home affordance, in every org-count case.
  if (organizations.length === 1) {
    return (
      <span
        title={triggerLabel}
        className="inline-flex max-w-[200px] flex-col justify-center gap-0.5 rounded-xs border border-transparent px-3 py-1.5"
      >
        <span className="truncate font-sans text-[13px] font-medium text-ink-900">
          {triggerLabel}
        </span>
        <span className="truncate font-sans text-[11px] tracking-[0.04em] text-ink-500">
          {ACCESS_LABEL}
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
        {organizations.length > 0 && (
          <>
            <DropdownMenuLabel className="text-[11px] tracking-[0.06em] text-ink-500 uppercase font-medium">
              Organizations
            </DropdownMenuLabel>
            {organizations.map((m) => {
              const isActive = m.organization_id === activeOrganization?.organization_id
              return (
                <DropdownMenuItem
                  key={m.organization_id}
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
                    {ACCESS_LABEL}
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
