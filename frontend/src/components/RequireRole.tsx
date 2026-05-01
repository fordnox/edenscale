import type { ReactNode } from "react"
import { Loader2 } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import type { components } from "@/lib/schema"

type UserRole = components["schemas"]["UserRole"]

interface RequireRoleProps {
  allowed: readonly UserRole[]
  children: ReactNode
  fallback?: ReactNode
}

export function RequireRole({ allowed, children, fallback }: RequireRoleProps) {
  const { activeMembership, isLoading } = useActiveOrganization()

  if (isLoading) {
    return (
      <div className="flex min-h-[280px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  const role = activeMembership?.role
  if (!role || !allowed.includes(role)) {
    if (fallback !== undefined) return <>{fallback}</>
    return (
      <div className="px-8 py-16">
        <Card>
          <EmptyState
            title="You do not have access to this page"
            body="This area is reserved for administrators and fund managers. Contact your administrator if you need access."
            action={
              <Button asChild variant="secondary" size="sm">
                <Link to="/">Back to dashboard</Link>
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
