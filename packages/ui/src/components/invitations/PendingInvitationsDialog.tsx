import { Loader2, MailCheck } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@edenscale/ui/dialog"
import { useActiveOrganization } from "@edenscale/shared/hooks/useActiveOrganization"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { formatRelativeDays } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"
import { usePendingInvitationsBanner } from "@edenscale/shared/contexts/PendingInvitationsBannerContext"

type InvitationRead = components["schemas"]["InvitationRead"]
type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Record<UserRole, string> = {
  superadmin: "Superadmin",
  admin: "Administrator",
  fund_manager: "Fund manager",
  lp: "Limited partner",
}

interface PendingInvitationsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  invitations: InvitationRead[]
}

export function PendingInvitationsDialog({
  open,
  onOpenChange,
  invitations,
}: PendingInvitationsDialogProps) {
  const { setActiveOrganizationId } = useActiveOrganization()
  const { decline } = usePendingInvitationsBanner()

  const acceptMutation = useApiMutation("post", "/invitations/accept", {
    onSuccess: (data) => {
      setActiveOrganizationId(data.organization_id)
      toast.success(`Welcome to ${data.organization.name}.`)
    },
  })

  function handleAccept(invitation: InvitationRead) {
    if (acceptMutation.isPending) return
    acceptMutation.mutate({ body: { token: invitation.token } })
  }

  function handleDecline(invitation: InvitationRead) {
    decline(invitation.id)
  }

  const today = new Date()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Pending invitations
          </DialogTitle>
          <DialogDescription>
            You&rsquo;ve been invited to join the following organization
            {invitations.length === 1 ? "" : "s"}. Accept to add it to your
            account.
          </DialogDescription>
        </DialogHeader>
        <ul className="flex flex-col gap-3">
          {invitations.map((invitation) => {
            const isAcceptingThis =
              acceptMutation.isPending &&
              acceptMutation.variables?.body.token === invitation.token
            const isAnyAccepting = acceptMutation.isPending
            return (
              <li
                key={invitation.id}
                className="flex flex-col gap-3 rounded-xs border border-[color:var(--border-hairline)] bg-parchment-50 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <span
                    aria-hidden
                    className="text-[color:var(--brass-700)] [&_svg]:size-5 [&_svg]:stroke-[1.5]"
                  >
                    <MailCheck />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-display text-[15px] font-medium text-ink-900">
                      {invitation.organization.name}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 font-sans text-[12px] text-ink-700">
                      <Badge tone="info">
                        {ROLE_LABELS[invitation.role]}
                      </Badge>
                      <span className="text-ink-500">
                        Expires{" "}
                        {formatRelativeDays(invitation.expires_at, today)}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2 self-end sm:self-center">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDecline(invitation)}
                    disabled={isAnyAccepting}
                  >
                    Decline
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={() => handleAccept(invitation)}
                    disabled={isAnyAccepting}
                  >
                    {isAcceptingThis && (
                      <Loader2
                        strokeWidth={1.5}
                        className="size-4 animate-spin"
                      />
                    )}
                    Accept
                  </Button>
                </div>
              </li>
            )
          })}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
