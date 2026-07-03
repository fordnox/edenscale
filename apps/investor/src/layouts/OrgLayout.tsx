import { useEffect } from "react"
import { Link, Outlet, useParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { PendingInvitationsBanner } from "@edenscale/ui/invitations/PendingInvitationsBanner"
import { CommandPalette } from "@/components/layout/CommandPalette"
import { TopNav } from "@/components/layout/TopNav"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useCommandPalette } from "@/hooks/useCommandPalette"
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
import { RESERVED_ORG_SLUGS } from "@/lib/investorRoutes"
import { setLastVisitedOrgSlug } from "@edenscale/shared/active-org"

// The manager app is a separate SPA behind the gateway — a react-router
// <Navigate> to /manager/* would only hit this app's wildcard route, so the
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

// The full application shell — a horizontal top nav (no sidebar) plus the
// command palette — shown once an org slug resolves to a fund the LP can view.
function OrgShell() {
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const { memberships } = useActiveOrganization()
  const { visibleInvitations, showBanner, dismissBanner } =
    usePendingInvitations()

  return (
    <div className="flex min-h-svh flex-col bg-page text-ink-900">
      <TopNav onOpenSearch={() => setPaletteOpen(true)} />
      {showBanner && (
        <PendingInvitationsBanner
          invitations={visibleInvitations}
          onDismiss={dismissBanner}
          emphasize={memberships.length === 0}
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
// active org, sends non-LP roles back to the manager app, and renders the shell.
export default function OrgLayout() {
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

  // The investor app is LP-only; managers belong in the manager app.
  if (membership?.role !== "lp") {
    return <CrossAppRedirect to={`/manager/${resolvedSlug}`} />
  }

  if (activeOrganizationId !== resolvedOrgId) {
    // Still syncing the active-org header — hold off on rendering the shell
    // (and its data-fetching children) until requests carry the right org.
    return <LoadingState />
  }

  return <OrgShell />
}
