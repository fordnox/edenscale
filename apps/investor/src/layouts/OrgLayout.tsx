import { useEffect } from "react"
import { Link, Outlet, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { PendingInvitationsBanner } from "@edenscale/ui/invitations/PendingInvitationsBanner"
import { CommandPalette } from "@/components/layout/CommandPalette"
import { TopNav } from "@/components/layout/TopNav"
import { useInvestorOrganizations } from "@/hooks/useInvestorOrganizations"
import { useCommandPalette } from "@edenscale/shared/hooks/useCommandPalette"
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
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

// The full application shell — a horizontal top nav (no sidebar) plus the
// command palette — shown once an org slug resolves to a fund the LP can view.
function OrgShell() {
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const { organizations } = useInvestorOrganizations()
  const { visibleInvitations, showBanner, dismissBanner } =
    usePendingInvitations()

  return (
    <div className="flex min-h-svh flex-col es-paper text-ink-900">
      <TopNav onOpenSearch={() => setPaletteOpen(true)} />
      {showBanner && (
        <PendingInvitationsBanner
          invitations={visibleInvitations}
          onDismiss={dismissBanner}
          emphasize={organizations.length === 0}
        />
      )}
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col">
        <Outlet />
      </main>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}

// Org view: resolves the :orgSlug param to an organization, syncs it as the
// active org, and renders the shell. Memberships are already LP-scoped by the
// provider, so an org where the user is only a manager simply doesn't resolve
// here — this app never routes to or reasons about the manager app.
export default function OrgLayout() {
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { organizations, isLoading, activeOrganizationId, setActiveOrganizationId } =
    useInvestorOrganizations()

  const isResolvableSlug = Boolean(orgSlug) && !RESERVED_ORG_SLUGS.has(orgSlug!)

  const membership = isResolvableSlug
    ? (organizations.find((m) => m.organization.slug === orgSlug) ?? null)
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

  if (activeOrganizationId !== resolvedOrgId) {
    // Still syncing the active-org header — hold off on rendering the shell
    // (and its data-fetching children) until requests carry the right org.
    return <LoadingState />
  }

  return <OrgShell />
}
