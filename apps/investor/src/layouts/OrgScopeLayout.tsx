import { useEffect } from "react"
import { Link, Navigate, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import AppShell from "@/layouts/AppShell"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { RESERVED_ORG_SLUGS } from "@/lib/investorRoutes"
import { setLastVisitedOrgSlug } from "@edenscale/shared/active-org"

function LoadingState() {
  return (
    <main className="flex-1 container mx-auto px-6 py-8">
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    </main>
  )
}

export default function OrgScopeLayout() {
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { memberships, isLoading, activeOrganizationId, setActiveOrganizationId } =
    useActiveOrganization()

  const isResolvableSlug = Boolean(orgSlug) && !RESERVED_ORG_SLUGS.has(orgSlug!)

  const membership = isResolvableSlug
    ? (memberships.find((m) => m.organization.slug === orgSlug) ?? null)
    : null

  const resolvedOrgId = membership?.organization_id ?? null
  const resolvedSlug = membership?.organization.slug ?? null

  useEffect(() => {
    if (!resolvedOrgId || !resolvedSlug) return
    if (activeOrganizationId !== resolvedOrgId) {
      setActiveOrganizationId(resolvedOrgId)
    }
    setLastVisitedOrgSlug(resolvedSlug)
  }, [resolvedOrgId, resolvedSlug, activeOrganizationId, setActiveOrganizationId])

  if (isLoading) {
    return <LoadingState />
  }

  if (!resolvedOrgId) {
    return (
      <div className="flex min-h-svh items-center justify-center px-8 py-16">
        <Card className="w-full max-w-xl">
          <EmptyState
            title="Organization not found"
            body="This organization doesn't exist, or you don't have access to it."
            action={
              <Button asChild variant="secondary" size="sm">
                <Link to="/investor">Back to your organizations</Link>
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  if (membership?.role !== "lp") {
    return <Navigate to={`/manager/${resolvedSlug}`} replace />
  }

  if (activeOrganizationId !== resolvedOrgId) {
    // Still syncing the active-org header — hold off on rendering the shell
    // (and its data-fetching children) until requests carry the right org.
    return <LoadingState />
  }

  return <AppShell />
}
