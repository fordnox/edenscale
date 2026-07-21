import { useEffect } from "react"
import { Link, Outlet, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { PendingInvitationsBanner } from "@edenscale/ui/invitations/PendingInvitationsBanner"
import { CommandPalette } from "@/components/layout/CommandPalette"
import { Topbar, type TopbarOrganization } from "@/components/layout/Topbar"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useCommandPalette } from "@edenscale/shared/hooks/useCommandPalette"
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
import { RESERVED_ORG_SLUGS } from "@/lib/managerRoutes"
import { setLastVisitedOrgSlug } from "@edenscale/shared/active-org"
import type { components } from "@edenscale/api/schema"

type UserRole = components["schemas"]["UserRole"]

function LoadingState() {
  return (
    <main className="flex-1 container mx-auto px-6 py-8">
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    </main>
  )
}

// The full application shell — top bar and command palette — shown once an
// organization slug has resolved to an org the current user can act on.
function OrgShell({
  organization,
  role,
}: {
  organization: TopbarOrganization
  role: UserRole | null
}) {
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const { memberships } = useActiveOrganization()
  const { visibleInvitations, showBanner, dismissBanner } =
    usePendingInvitations()

  return (
    <div className="flex min-h-svh flex-col bg-page text-ink-900">
      <Topbar
        organization={organization}
        role={role}
        onOpenSearch={() => setPaletteOpen(true)}
      />
      {showBanner && (
        <PendingInvitationsBanner
          invitations={visibleInvitations}
          onDismiss={dismissBanner}
          emphasize={memberships.length === 0}
        />
      )}
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}

// Org view: resolves the :orgSlug param to an organization, syncs it as the
// active org (so requests carry the right X-Organization-Id header), and then
// renders the application shell. Memberships are already manager-scoped by the
// provider, so an org where the user is only an LP simply doesn't resolve
// here — this app never routes to or reasons about the investor app.
export default function OrgLayout() {
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const {
    memberships,
    isLoading,
    activeOrganizationId,
    setActiveOrganizationId,
  } = useActiveOrganization()

  const isResolvableSlug = Boolean(orgSlug) && !RESERVED_ORG_SLUGS.has(orgSlug!)

  const membership = isResolvableSlug
    ? (memberships.find((m) => m.organization.slug === orgSlug) ?? null)
    : null

  const resolvedOrgId = membership?.organization_id ?? null
  const resolvedSlug = membership?.organization.slug ?? null
  const resolvedName = membership?.organization.name ?? null
  const role: UserRole | null = membership?.role ?? null

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
                <Link to="/manager">Back to your organizations</Link>
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  if (activeOrganizationId !== resolvedOrgId) {
    // Still syncing the active-org header — hold off on rendering the shell
    // (and its data-fetching children) until requests carry the right org.
    return <LoadingState />
  }

  return (
    <OrgShell
      organization={{
        name: resolvedName ?? resolvedSlug ?? "",
        slug: resolvedSlug ?? "",
      }}
      role={role}
    />
  )
}
