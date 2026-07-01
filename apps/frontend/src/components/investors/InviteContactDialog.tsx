import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useApiMutation } from "@/hooks/useApiMutation"
import type { components } from "@/lib/schema"

type InvestorContactRead = components["schemas"]["InvestorContactRead"]

interface InviteContactDialogProps {
  contact: InvestorContactRead
  organizationId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function InviteContactDialog({
  contact,
  organizationId,
  open,
  onOpenChange,
}: InviteContactDialogProps) {
  const queryClient = useQueryClient()

  const createInvitation = useApiMutation("post", "/invitations", {
    onSuccess: (data) => {
      toast.success(
        `Invitation sent. ${data.email} will receive an email to set up access.`,
      )
      queryClient.invalidateQueries({ queryKey: ["/invitations"] })
      onOpenChange(false)
    },
  })

  function handleOpenChange(next: boolean) {
    if (!next && createInvitation.isPending) return
    onOpenChange(next)
  }

  function handleSend() {
    if (createInvitation.isPending || !contact.email) return
    createInvitation.mutate({
      body: {
        email: contact.email,
        role: "lp",
        organization_id: organizationId,
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Invite {contact.first_name} {contact.last_name}
          </DialogTitle>
          <DialogDescription>
            We&rsquo;ll email {contact.email} a one-time invitation to sign in
            as a limited partner. Once accepted, their login is linked to this
            contact automatically and scoped to this investor&rsquo;s
            commitments.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => handleOpenChange(false)}
            disabled={createInvitation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={handleSend}
            disabled={createInvitation.isPending || !contact.email}
          >
            {createInvitation.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Send invitation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
