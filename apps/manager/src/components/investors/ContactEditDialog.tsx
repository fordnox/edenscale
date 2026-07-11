import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { ArrowUpRight, Loader2, Mail } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@edenscale/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@edenscale/ui/dialog"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { orgPath } from "@/lib/managerRoutes"
import type { components } from "@edenscale/api/schema"

type InvestorContactRead = components["schemas"]["InvestorContactRead"]
type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Partial<Record<UserRole, string>> = {
  admin: "Admin",
  fund_manager: "Fund manager",
  lp: "LP",
}

// Sentinel for the "Not linked" option — Radix Select forbids an empty-string
// value, so unlinked state is carried as this literal and mapped to null.
const UNLINKED = "none"

interface ContactEditDialogProps {
  contact: InvestorContactRead
  investorId: string
  canInvite: boolean
  open: boolean
  onOpenChange: (open: boolean) => void
  onInvite: () => void
}

export function ContactEditDialog({
  contact,
  investorId,
  canInvite,
  open,
  onOpenChange,
  onInvite,
}: ContactEditDialogProps) {
  const queryClient = useQueryClient()

  const [firstName, setFirstName] = useState(contact.first_name)
  const [lastName, setLastName] = useState(contact.last_name)
  const [email, setEmail] = useState(contact.email ?? "")
  const [phone, setPhone] = useState(contact.phone ?? "")
  const [title, setTitle] = useState(contact.title ?? "")
  const [linkedUserId, setLinkedUserId] = useState<string>(
    contact.user_id ?? UNLINKED,
  )

  useEffect(() => {
    if (!open) return
    setFirstName(contact.first_name)
    setLastName(contact.last_name)
    setEmail(contact.email ?? "")
    setPhone(contact.phone ?? "")
    setTitle(contact.title ?? "")
    setLinkedUserId(contact.user_id ?? UNLINKED)
  }, [open, contact])

  // Inviting reads the persisted email, so block it while the field is dirty —
  // the manager should save the new address first.
  const emailDirty = email.trim() !== (contact.email ?? "")

  // Any member of this organization can be linked — admins and fund managers
  // included, since a fund's administrator is often also an investor. The link
  // is what grants the contact-scoped view in the investor portal.
  const membersQuery = useApiQuery("/users", undefined, { enabled: open })
  const members = membersQuery.data ?? []
  // Keep an already-linked user selectable even if they're not in the member
  // list (e.g. a historical link), so saving an unrelated edit never drops the
  // link.
  const linkedUserMissing =
    contact.user_id !== null && !members.some((m) => m.id === contact.user_id)

  const { activeMembership } = useActiveOrganization()
  const orgSlug = activeMembership?.organization.slug ?? null
  // Deep link to the invitations section of organization settings (the same
  // #invitations anchor rendered there).
  const invitationsHref = orgSlug
    ? `${orgPath(orgSlug, "settings")}#invitations`
    : null

  const updateContact = useApiMutation(
    "patch",
    "/investors/{investor_id}/contacts/{contact_id}",
    {
      onSuccess: () => {
        toast.success("Contact updated")
        queryClient.invalidateQueries({
          queryKey: [
            "/investors/{investor_id}/contacts",
            { params: { path: { investor_id: investorId } } },
          ],
        })
        queryClient.invalidateQueries({ queryKey: ["/investors"] })
        queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
        onOpenChange(false)
      },
    },
  )

  function handleOpenChange(next: boolean) {
    if (!next && updateContact.isPending) return
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!firstName.trim() || !lastName.trim() || updateContact.isPending) return
    updateContact.mutate({
      params: { path: { investor_id: investorId, contact_id: contact.id } },
      body: {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim() || null,
        phone: phone.trim() || null,
        title: title.trim() || null,
        // Explicit link to a member of this org (or null to unlink).
        user_id: linkedUserId === UNLINKED ? null : linkedUserId,
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">Edit contact</DialogTitle>
          <DialogDescription>
            Update this contact&rsquo;s details and link them to a member of
            your organization, or invite them if they don&rsquo;t have an
            account yet.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="contact-edit-first-name">First name</Label>
              <Input
                id="contact-edit-first-name"
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="contact-edit-last-name">Last name</Label>
              <Input
                id="contact-edit-last-name"
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="contact-edit-title">Title</Label>
              <Input
                id="contact-edit-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="contact-edit-email">Email</Label>
              <Input
                id="contact-edit-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="contact-edit-phone">Phone</Label>
            <Input
              id="contact-edit-phone"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2 border-t border-[color:var(--border-hairline)] pt-4">
            <Label htmlFor="contact-edit-user">Linked user</Label>
            <Select value={linkedUserId} onValueChange={setLinkedUserId}>
              <SelectTrigger id="contact-edit-user" className="w-full">
                <SelectValue placeholder="Not linked" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNLINKED}>Not linked</SelectItem>
                {linkedUserMissing && contact.user_id && (
                  <SelectItem value={contact.user_id}>
                    Currently linked user
                  </SelectItem>
                )}
                {members.map((member) => (
                  <SelectItem key={member.id} value={String(member.id)}>
                    {member.first_name} {member.last_name}
                    {member.email ? ` · ${member.email}` : ""}
                    {` · ${ROLE_LABELS[member.role] ?? member.role}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="font-sans text-[12px] text-ink-500">
              Any member of this organization can be linked — including admins
              and fund managers who are themselves investors. The linked user
              sees this investor&rsquo;s data in the investor portal.
            </p>

            {linkedUserId === UNLINKED && (
              <div className="mt-1 flex flex-col gap-2">
                {canInvite ? (
                  <>
                    <p className="font-sans text-[12px] text-ink-500">
                      Not in the list? Invite them by email to set up access.
                    </p>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="w-fit"
                      disabled={!email.trim() || emailDirty}
                      onClick={onInvite}
                    >
                      <Mail strokeWidth={1.5} className="size-4" />
                      Send invitation
                    </Button>
                    {!email.trim() && (
                      <p className="font-sans text-[12px] text-ink-500">
                        Add an email address to invite this contact.
                      </p>
                    )}
                    {email.trim() && emailDirty && (
                      <p className="font-sans text-[12px] text-ink-500">
                        Save your changes before sending an invitation.
                      </p>
                    )}
                    {invitationsHref && (
                      <Link
                        to={invitationsHref}
                        onClick={() => handleOpenChange(false)}
                        className="inline-flex w-fit items-center gap-1 font-sans text-[12px] text-conifer-700 underline-offset-4 hover:underline focus-visible:underline focus-visible:outline-none"
                      >
                        Manage pending invitations
                        <ArrowUpRight strokeWidth={1.5} className="size-3.5" />
                      </Link>
                    )}
                  </>
                ) : (
                  <p className="font-sans text-[12px] text-ink-500">
                    An admin can invite this contact to the portal.
                  </p>
                )}
              </div>
            )}
          </div>

          <DialogFooter className="pb-[env(safe-area-inset-bottom)]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => handleOpenChange(false)}
              disabled={updateContact.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={
                updateContact.isPending ||
                !firstName.trim() ||
                !lastName.trim()
              }
            >
              {updateContact.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
