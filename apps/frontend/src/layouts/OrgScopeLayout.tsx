import { useEffect } from "react"
import { Link, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import AppShell from "@/layouts/AppShell"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { RESERVED_ORG_SLUGS } from "@/lib/appRoutes"
import { setLastVisitedOrgSlug } from "@/lib/activeOrg"

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

  const membership =
    orgSlug && !RESERVED_ORG_SLUGS.has(orgSlug)
      ? (memberships.find((m) => m.organization.slug === orgSlug) ?? null)
      : null

  useEffect(() => {
    if (!membership) return
    if (activeOrganizationId !== membership.organization_id) {
      setActiveOrganizationId(membership.organization_id)
    }
    setLastVisitedOrgSlug(membership.organization.slug)
  }, [membership, activeOrganizationId, setActiveOrganizationId])

  if (isLoading) {
    return <LoadingState />
  }

  if (!membership) {
    return (
      <div className="flex min-h-svh items-center justify-center px-8 py-16">
        <Card className="w-full max-w-xl">
          <EmptyState
            title="Organization not found"
            body="This organization doesn't exist, or you don't have access to it."
            action={
              <Button asChild variant="secondary" size="sm">
                <Link to="/app">Back to your organizations</Link>
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  if (activeOrganizationId !== membership.organization_id) {
    // Still syncing the active-org header — hold off on rendering the shell
    // (and its data-fetching children) until requests carry the right org.
    return <LoadingState />
  }

  return <AppShell />
}
