import { useEffect, useMemo } from "react"
import { Link, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import AppShell from "@/layouts/AppShell"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { RESERVED_ORG_SLUGS } from "@/lib/managerRoutes"
import { setLastVisitedOrgSlug } from "@edenscale/shared/active-org"

// The investor app is a separate SPA behind the gateway — a react-router
// <Navigate> to /investor/* would only hit this app's wildcard route, so the
// role redirect must be a full document navigation.
function CrossAppRedirect({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to)
  }, [to])
  return <LoadingState />
}

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
  const {
    memberships,
    isLoading,
    isSuperadmin,
    activeOrganizationId,
    setActiveOrganizationId,
  } = useActiveOrganization()

  const isResolvableSlug = Boolean(orgSlug) && !RESERVED_ORG_SLUGS.has(orgSlug!)

  const membership = isResolvableSlug
    ? (memberships.find((m) => m.organization.slug === orgSlug) ?? null)
    : null

  // A superadmin can act on any org even without a tenant membership row (the
  // backend synthesizes a transient superadmin membership for the header).
  // Resolve the slug to an org id via the superadmin org list so we can set
  // the active-org header; only needed when no real membership matched.
  const needsSuperadminResolve =
    isResolvableSlug && !membership && isSuperadmin
  const superadminOrgsQuery = useApiQuery("/superadmin/organizations", undefined, {
    enabled: needsSuperadminResolve,
  })
  const superadminOrg = useMemo(
    () =>
      needsSuperadminResolve
        ? (superadminOrgsQuery.data?.find((o) => o.slug === orgSlug) ?? null)
        : null,
    [needsSuperadminResolve, superadminOrgsQuery.data, orgSlug],
  )

  const resolvedOrgId = membership?.organization_id ?? superadminOrg?.id ?? null
  const resolvedSlug = membership?.organization.slug ?? superadminOrg?.slug ?? null

  useEffect(() => {
    if (!resolvedOrgId || !resolvedSlug) return
    if (activeOrganizationId !== resolvedOrgId) {
      setActiveOrganizationId(resolvedOrgId)
    }
    setLastVisitedOrgSlug(resolvedSlug)
  }, [resolvedOrgId, resolvedSlug, activeOrganizationId, setActiveOrganizationId])

  if (isLoading || (needsSuperadminResolve && superadminOrgsQuery.isLoading)) {
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
                <Link to="/manager">Back to your organizations</Link>
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  if (membership?.role === "lp" && !isSuperadmin) {
    return <CrossAppRedirect to={`/investor/${resolvedSlug}`} />
  }

  if (activeOrganizationId !== resolvedOrgId) {
    // Still syncing the active-org header — hold off on rendering the shell
    // (and its data-fetching children) until requests carry the right org.
    return <LoadingState />
  }

  return <AppShell />
}
