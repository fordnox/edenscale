import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useQueryClient } from "@tanstack/react-query"
import {
  Check,
  Loader2,
  Mail,
  Pencil,
  Plus,
  RotateCw,
  Trash2,
  Users,
  X as XIcon,
} from "lucide-react"
import { toast } from "sonner"

import { RequireRole } from "@/components/RequireRole"
import { PageHero } from "@edenscale/ui/PageHero"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@edenscale/ui/alert-dialog"
import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@edenscale/ui/dialog"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { Textarea } from "@edenscale/ui/textarea"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatRelativeDays } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type UserRole = components["schemas"]["UserRole"]
type OrgMemberRead = components["schemas"]["OrgMemberRead"]
type FundGroupRead = components["schemas"]["FundGroupRead"]
type OrganizationType = components["schemas"]["OrganizationType"]
type InvitationListItem = components["schemas"]["InvitationListItem"]
type InvitationStatus = components["schemas"]["InvitationStatus"]

const ROLE_LABELS: Record<UserRole, string> = {
  superadmin: "Superadmin",
  admin: "Administrator",
  fund_manager: "Fund manager",
  lp: "Limited partner",
}

const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  superadmin: "Platform-level access across all organizations.",
  admin: "Full access to organization settings, audit log, and all organization data.",
  fund_manager: "Manages funds, investors, capital activity, and team members.",
  lp: "Read-only access to your commitments, documents, and letters.",
}

const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  fund_manager_firm: "Fund manager organization",
  investor_firm: "Investor organization",
  service_provider: "Service provider",
}

const STATUS_LABELS: Record<InvitationStatus, string> = {
  pending: "Pending",
  accepted: "Accepted",
  revoked: "Revoked",
  expired: "Expired",
}

type BadgeTone = "active" | "muted" | "warning" | "negative"

const STATUS_TONES: Record<InvitationStatus, BadgeTone> = {
  pending: "warning",
  accepted: "active",
  revoked: "muted",
  expired: "negative",
}

function fullName(user: OrgMemberRead) {
  const name = `${user.first_name} ${user.last_name}`.trim()
  return name || user.email
}

export default function OrganizationSettingsPage() {
  return (
    <RequireRole allowed={["admin", "fund_manager"]}>
      <OrganizationSettingsContent />
    </RequireRole>
  )
}

function OrganizationSettingsContent() {
  const queryClient = useQueryClient()

  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const me = meQuery.data
  const { activeMembership, isLoading: isMembershipLoading } =
    useActiveOrganization()

  const orgId = activeMembership?.organization_id ?? null
  const activeRole = activeMembership?.role
  const isAdmin = activeRole === "admin"
  const isFundManager = activeRole === "fund_manager"
  const isSuperadmin = me?.is_superadmin === true

  const orgQuery = useApiQuery(
    "/organizations/{organization_id}",
    { params: { path: { organization_id: orgId ?? "" } } },
    { enabled: orgId !== null },
  )

  const usersQuery = useApiQuery("/users", undefined, {
    enabled: activeMembership !== null && (isAdmin || isFundManager),
  })

  const [name, setName] = useState("")
  const [legalName, setLegalName] = useState("")
  const [taxId, setTaxId] = useState("")
  const [website, setWebsite] = useState("")
  const [description, setDescription] = useState("")

  const [inviteOpen, setInviteOpen] = useState(false)

  const org = orgQuery.data

  useEffect(() => {
    if (!org) return
    setName(org.name)
    setLegalName(org.legal_name ?? "")
    setTaxId(org.tax_id ?? "")
    setWebsite(org.website ?? "")
    setDescription(org.description ?? "")
  }, [org])

  const updateOrg = useApiMutation(
    "patch",
    "/organizations/{organization_id}",
    {
      onSuccess: () => {
        toast.success("Organization updated")
        queryClient.invalidateQueries({
          queryKey: ["/organizations/{organization_id}"],
        })
        queryClient.invalidateQueries({ queryKey: ["/organizations"] })
      },
    },
  )

  const updateRole = useApiMutation("patch", "/users/{user_id}/role", {
    onSuccess: () => {
      toast.success("Role updated")
      queryClient.invalidateQueries({ queryKey: ["/users"] })
      queryClient.invalidateQueries({ queryKey: ["/users/me"] })
    },
  })

  const invitationsQuery = useApiQuery("/invitations", undefined, {
    enabled: orgId !== null && isAdmin,
  })

  const resendInvitation = useApiMutation(
    "post",
    "/invitations/{invitation_id}/resend",
    {
      onSuccess: (data) => {
        toast.success(`Invitation resent to ${data.email}.`)
        queryClient.invalidateQueries({ queryKey: ["/invitations"] })
      },
    },
  )

  const revokeInvitation = useApiMutation(
    "post",
    "/invitations/{invitation_id}/revoke",
    {
      onSuccess: (data) => {
        toast.success(`Invitation to ${data.email} revoked.`)
        queryClient.invalidateQueries({ queryKey: ["/invitations"] })
      },
    },
  )

  const isDirty = useMemo(() => {
    if (!org) return false
    return (
      name.trim() !== org.name ||
      legalName.trim() !== (org.legal_name ?? "") ||
      taxId.trim() !== (org.tax_id ?? "") ||
      website.trim() !== (org.website ?? "") ||
      description.trim() !== (org.description ?? "")
    )
  }, [org, name, legalName, taxId, website, description])

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!org || !isDirty || updateOrg.isPending) return
    if (!name.trim()) {
      toast.error("Name is required")
      return
    }
    updateOrg.mutate({
      params: { path: { organization_id: org.id } },
      body: {
        name: name.trim(),
        legal_name: legalName.trim() ? legalName.trim() : null,
        tax_id: taxId.trim() ? taxId.trim() : null,
        website: website.trim() ? website.trim() : null,
        description: description.trim() ? description.trim() : null,
      },
    })
  }

  function handleReset() {
    if (!org) return
    setName(org.name)
    setLegalName(org.legal_name ?? "")
    setTaxId(org.tax_id ?? "")
    setWebsite(org.website ?? "")
    setDescription(org.description ?? "")
  }

  function handleRoleChange(user: OrgMemberRead, nextRole: UserRole) {
    if (user.role === nextRole) return
    if (me && user.id === me.id) {
      toast.error("You cannot change your own role")
      return
    }
    updateRole.mutate({
      params: { path: { user_id: user.id } },
      body: { role: nextRole },
    })
  }

  const teamMembers = useMemo(() => {
    return (usersQuery.data ?? []).slice().sort((a, b) => {
      const an = fullName(a).toLowerCase()
      const bn = fullName(b).toLowerCase()
      return an.localeCompare(bn)
    })
  }, [usersQuery.data])

  const userById = useMemo(() => {
    const map = new Map<string, OrgMemberRead>()
    for (const user of usersQuery.data ?? []) map.set(user.id, user)
    return map
  }, [usersQuery.data])

  const invitations = useMemo(() => {
    const list = (invitationsQuery.data ?? []).slice()
    list.sort((a, b) => {
      if (a.status === "pending" && b.status !== "pending") return -1
      if (a.status !== "pending" && b.status === "pending") return 1
      const ad = a.created_at ? Date.parse(a.created_at) : 0
      const bd = b.created_at ? Date.parse(b.created_at) : 0
      return bd - ad
    })
    return list
  }, [invitationsQuery.data])

  function handleResend(invitation: InvitationListItem) {
    if (resendInvitation.isPending || revokeInvitation.isPending) return
    resendInvitation.mutate({
      params: { path: { invitation_id: invitation.id } },
    })
  }

  function handleRevoke(invitation: InvitationListItem) {
    if (resendInvitation.isPending || revokeInvitation.isPending) return
    revokeInvitation.mutate({
      params: { path: { invitation_id: invitation.id } },
    })
  }

  return (
    <>
      <Helmet>
        <title>{`Organization · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Settings"
        title="Organization."
        description="Update organization details and manage who has access. Changes apply across the workspace."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {meQuery.isLoading || isMembershipLoading || orgQuery.isLoading ? (
          <div className="flex min-h-[280px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : orgId === null ? (
          <Card>
            <EmptyState
              icon={<Users strokeWidth={1.25} />}
              title="No organization on file"
              body="Your account is not associated with an organization. Contact support or your administrator to be assigned."
            />
          </Card>
        ) : !org ? (
          <Card>
            <CardSection>
              <p className="font-sans text-[14px] text-ink-700">
                Could not load organization details.
              </p>
            </CardSection>
          </Card>
        ) : (
          <div className="mx-auto flex max-w-5xl flex-col gap-6">
            <Card>
              <CardSection>
                <Eyebrow>Your access</Eyebrow>
                <div className="mt-4 flex flex-col gap-3">
                  <div className="flex items-center gap-3">
                    <Badge tone="info">
                      {activeRole ? ROLE_LABELS[activeRole] : "—"}
                    </Badge>
                    {activeRole && (
                      <span className="font-sans text-[13px] text-ink-700">
                        {ROLE_DESCRIPTIONS[activeRole]}
                      </span>
                    )}
                  </div>
                  <p className="font-sans text-[12px] text-ink-500">
                    Roles are managed by your administrator. Contact them if
                    your access needs to change.
                  </p>
                </div>
              </CardSection>
            </Card>

            <Card>
              <CardSection>
                <div className="flex items-baseline justify-between gap-3">
                  <Eyebrow>Organization details</Eyebrow>
                  <Badge tone="muted">{ORG_TYPE_LABELS[org.type]}</Badge>
                </div>
                <form
                  onSubmit={handleSubmit}
                  className="mt-5 flex flex-col gap-5"
                >
                  <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="org-name">Name</Label>
                      <Input
                        id="org-name"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="org-legal-name">Legal name</Label>
                      <Input
                        id="org-legal-name"
                        value={legalName}
                        onChange={(event) => setLegalName(event.target.value)}
                        placeholder="Eden Capital Partners, LP"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="org-tax-id">Tax ID</Label>
                      <Input
                        id="org-tax-id"
                        value={taxId}
                        onChange={(event) => setTaxId(event.target.value)}
                        placeholder="EIN / VAT / TIN"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="org-website">Website</Label>
                      <Input
                        id="org-website"
                        value={website}
                        onChange={(event) => setWebsite(event.target.value)}
                        placeholder="https://example.com"
                        autoComplete="url"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5 md:col-span-2">
                      <Label htmlFor="org-description">Description</Label>
                      <Textarea
                        id="org-description"
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                        rows={3}
                        placeholder="Investment thesis, mandate, or short bio."
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 border-t border-[color:var(--border-hairline)] pt-5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleReset}
                      disabled={!isDirty || updateOrg.isPending}
                    >
                      Reset
                    </Button>
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={!isDirty || updateOrg.isPending}
                    >
                      {updateOrg.isPending && (
                        <Loader2
                          strokeWidth={1.5}
                          className="size-4 animate-spin"
                        />
                      )}
                      Save changes
                    </Button>
                  </div>
                </form>
              </CardSection>
            </Card>

            <Card>
              <div className="flex items-end justify-between gap-4 px-6 pt-6 md:px-8 md:pt-8">
                <div className="flex flex-col gap-1.5">
                  <Eyebrow>Team</Eyebrow>
                  <p className="font-sans text-[13px] text-ink-700">
                    {isAdmin
                      ? "Administrators can change roles. Fund managers can invite new users."
                      : "Fund managers can invite new users. Only administrators can change roles."}
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setInviteOpen(true)}
                >
                  <Plus strokeWidth={1.5} className="size-4" />
                  Invite user
                </Button>
              </div>
              <CardSection className="pt-4">
                {usersQuery.isLoading ? (
                  <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                    <Loader2
                      strokeWidth={1.5}
                      className="size-6 animate-spin"
                    />
                  </div>
                ) : teamMembers.length === 0 ? (
                  <EmptyState
                    icon={<Users strokeWidth={1.25} />}
                    title="No team members yet"
                    body="Invite the first member of your organization to get started."
                  />
                ) : (
                  <DataTable>
                    <thead>
                      <tr>
                        <TH>Name</TH>
                        <TH>Email</TH>
                        <TH>Title</TH>
                        <TH>Role</TH>
                        <TH>Status</TH>
                      </tr>
                    </thead>
                    <tbody>
                      {teamMembers.map((user) => {
                        const isSelf = me ? user.id === me.id : false
                        const canEditRole = isAdmin && !isSelf
                        return (
                          <TR key={user.id}>
                            <TD primary>{fullName(user)}</TD>
                            <TD>{user.email}</TD>
                            <TD>{user.title ?? "—"}</TD>
                            <TD>
                              {canEditRole ? (
                                <Select
                                  value={user.role}
                                  onValueChange={(value) =>
                                    handleRoleChange(user, value as UserRole)
                                  }
                                >
                                  <SelectTrigger
                                    aria-label={`Change role for ${fullName(user)}`}
                                    className="w-[160px]"
                                  >
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {(
                                      ["admin", "fund_manager", "lp"] as const
                                    ).map((role) => (
                                      <SelectItem key={role} value={role}>
                                        {ROLE_LABELS[role]}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              ) : (
                                <Badge tone="info">{ROLE_LABELS[user.role]}</Badge>
                              )}
                            </TD>
                            <TD>
                              {user.is_active ? (
                                <Badge tone="active">Active</Badge>
                              ) : (
                                <Badge tone="muted">Inactive</Badge>
                              )}
                            </TD>
                          </TR>
                        )
                      })}
                    </tbody>
                  </DataTable>
                )}
              </CardSection>
            </Card>

            {(isAdmin || isFundManager) && <FundGroupsCard />}

            {isAdmin && (
              <Card>
                <div className="flex items-end justify-between gap-4 px-6 pt-6 md:px-8 md:pt-8">
                  <div className="flex flex-col gap-1.5">
                    <Eyebrow>Pending invitations</Eyebrow>
                    <p className="font-sans text-[13px] text-ink-700">
                      People you&rsquo;ve invited who haven&rsquo;t joined yet.
                      Resend the email or revoke if you change your mind.
                    </p>
                  </div>
                </div>
                <CardSection className="pt-4">
                  {invitationsQuery.isLoading ? (
                    <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                      <Loader2
                        strokeWidth={1.5}
                        className="size-6 animate-spin"
                      />
                    </div>
                  ) : invitations.length === 0 ? (
                    <EmptyState
                      icon={<Mail strokeWidth={1.25} />}
                      title="No invitations"
                      body="When you invite someone, they'll appear here until they accept."
                    />
                  ) : (
                    <DataTable>
                      <thead>
                        <tr>
                          <TH>Email</TH>
                          <TH>Role</TH>
                          <TH>Invited by</TH>
                          <TH>Expires</TH>
                          <TH>Status</TH>
                          <TH align="right">Actions</TH>
                        </tr>
                      </thead>
                      <tbody>
                        {invitations.map((invitation) => {
                          const inviter =
                            invitation.invited_by_user_id !== null
                              ? userById.get(invitation.invited_by_user_id)
                              : undefined
                          const isPending = invitation.status === "pending"
                          const isMutating =
                            (resendInvitation.isPending &&
                              resendInvitation.variables?.params.path
                                .invitation_id === invitation.id) ||
                            (revokeInvitation.isPending &&
                              revokeInvitation.variables?.params.path
                                .invitation_id === invitation.id)
                          return (
                            <TR key={invitation.id}>
                              <TD primary>{invitation.email}</TD>
                              <TD>
                                <Badge tone="info">
                                  {ROLE_LABELS[invitation.role]}
                                </Badge>
                              </TD>
                              <TD>{inviter ? fullName(inviter) : "—"}</TD>
                              <TD>
                                {formatRelativeDays(
                                  invitation.expires_at,
                                  new Date(),
                                )}
                              </TD>
                              <TD>
                                <Badge
                                  tone={STATUS_TONES[invitation.status]}
                                >
                                  {STATUS_LABELS[invitation.status]}
                                </Badge>
                              </TD>
                              <TD align="right">
                                {isPending ? (
                                  <div className="flex items-center justify-end gap-2">
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleResend(invitation)}
                                      disabled={isMutating}
                                    >
                                      {resendInvitation.isPending &&
                                      resendInvitation.variables?.params.path
                                        .invitation_id === invitation.id ? (
                                        <Loader2
                                          strokeWidth={1.5}
                                          className="size-4 animate-spin"
                                        />
                                      ) : (
                                        <RotateCw
                                          strokeWidth={1.5}
                                          className="size-4"
                                        />
                                      )}
                                      Resend
                                    </Button>
                                    <Button
                                      type="button"
                                      variant="secondary"
                                      size="sm"
                                      onClick={() => handleRevoke(invitation)}
                                      disabled={isMutating}
                                    >
                                      {revokeInvitation.isPending &&
                                      revokeInvitation.variables?.params.path
                                        .invitation_id === invitation.id ? (
                                        <Loader2
                                          strokeWidth={1.5}
                                          className="size-4 animate-spin"
                                        />
                                      ) : (
                                        <XIcon
                                          strokeWidth={1.5}
                                          className="size-4"
                                        />
                                      )}
                                      Revoke
                                    </Button>
                                  </div>
                                ) : (
                                  <span className="text-ink-500">—</span>
                                )}
                              </TD>
                            </TR>
                          )
                        })}
                      </tbody>
                    </DataTable>
                  )}
                </CardSection>
              </Card>
            )}
          </div>
        )}
      </div>

      <InviteUserDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        defaultOrganizationId={orgId}
        isSuperadmin={isSuperadmin}
      />
    </>
  )
}

type InvitableRole = Exclude<UserRole, "superadmin">

const INVITABLE_ROLES: readonly InvitableRole[] = [
  "admin",
  "fund_manager",
  "lp",
] as const

interface InviteUserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultOrganizationId: string | null
  isSuperadmin: boolean
}

function InviteUserDialog({
  open,
  onOpenChange,
  defaultOrganizationId,
  isSuperadmin,
}: InviteUserDialogProps) {
  const queryClient = useQueryClient()

  const [email, setEmail] = useState("")
  const [role, setRole] = useState<InvitableRole>("fund_manager")
  const [organizationId, setOrganizationId] = useState<string>(
    defaultOrganizationId ?? "",
  )

  useEffect(() => {
    setOrganizationId(defaultOrganizationId ?? "")
  }, [defaultOrganizationId])

  const orgsQuery = useApiQuery("/organizations", undefined, {
    enabled: open && isSuperadmin,
  })

  const createInvitation = useApiMutation("post", "/invitations", {
    onSuccess: (data) => {
      toast.success(
        `Invitation sent. ${data.email} will receive an email to join.`,
      )
      queryClient.invalidateQueries({ queryKey: ["/invitations"] })
      reset()
      onOpenChange(false)
    },
  })

  function reset() {
    setEmail("")
    setRole("fund_manager")
    setOrganizationId(defaultOrganizationId ?? "")
  }

  function handleOpenChange(next: boolean) {
    if (!next && createInvitation.isPending) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (createInvitation.isPending) return
    if (!email.trim()) {
      toast.error("Email is required")
      return
    }

    const orgIdValue = isSuperadmin
      ? organizationId || null
      : defaultOrganizationId

    if (orgIdValue === null) {
      toast.error("Choose an organization for this invitation")
      return
    }

    createInvitation.mutate({
      body: {
        email: email.trim(),
        role,
        organization_id: orgIdValue,
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Invite user
          </DialogTitle>
          <DialogDescription>
            We&rsquo;ll email a one-time invitation link. The recipient signs
            in, accepts, and completes their profile from there.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              autoFocus
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="invite-role">Role</Label>
            <Select
              value={role}
              onValueChange={(value) => setRole(value as InvitableRole)}
            >
              <SelectTrigger id="invite-role" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INVITABLE_ROLES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {ROLE_LABELS[value]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {isSuperadmin && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-org">Organization</Label>
              <Select
                value={organizationId}
                onValueChange={setOrganizationId}
              >
                <SelectTrigger id="invite-org" className="w-full">
                  <SelectValue placeholder="Choose an organization" />
                </SelectTrigger>
                <SelectContent>
                  {(orgsQuery.data ?? []).map((organization) => (
                    <SelectItem
                      key={organization.id}
                      value={String(organization.id)}
                    >
                      {organization.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
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
              type="submit"
              variant="primary"
              size="sm"
              disabled={createInvitation.isPending || !email.trim()}
            >
              {createInvitation.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Send invitation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function FundGroupsCard() {
  const queryClient = useQueryClient()
  const groupsQuery = useApiQuery("/fund-groups")
  const groups = groupsQuery.data ?? []

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [groupToDelete, setGroupToDelete] = useState<FundGroupRead | null>(null)

  const updateGroup = useApiMutation("patch", "/fund-groups/{fund_group_id}", {
    onSuccess: () => {
      toast.success("Fund group renamed")
      queryClient.invalidateQueries({ queryKey: ["/fund-groups"] })
      setEditingId(null)
      setEditName("")
    },
  })

  const deleteGroup = useApiMutation("delete", "/fund-groups/{fund_group_id}", {
    onSuccess: () => {
      toast.success("Fund group deleted")
      queryClient.invalidateQueries({ queryKey: ["/fund-groups"] })
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      setGroupToDelete(null)
    },
  })

  function startEdit(group: FundGroupRead) {
    setEditingId(group.id)
    setEditName(group.name)
  }

  function saveEdit(group: FundGroupRead) {
    const trimmed = editName.trim()
    if (!trimmed || updateGroup.isPending) return
    updateGroup.mutate({
      params: { path: { fund_group_id: group.id } },
      body: { name: trimmed },
    })
  }

  return (
    <>
      <Card>
        <div className="flex items-end justify-between gap-4 px-6 pt-6 md:px-8 md:pt-8">
          <div className="flex flex-col gap-1.5">
            <Eyebrow>Fund groups</Eyebrow>
            <p className="font-sans text-[13px] text-ink-700">
              Organize funds into families or vintages. Create groups from the
              fund dialog; rename or remove them here.
            </p>
          </div>
        </div>
        <CardSection className="pt-4">
          {groupsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
            </div>
          ) : groups.length === 0 ? (
            <EmptyState
              icon={<Users strokeWidth={1.25} />}
              title="No fund groups yet"
              body="Create a group while adding or editing a fund to see it here."
            />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Name</TH>
                  <TH align="right">Actions</TH>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => {
                  const isEditing = editingId === group.id
                  return (
                    <TR key={group.id}>
                      <TD primary>
                        {isEditing ? (
                          <Input
                            value={editName}
                            onChange={(event) => setEditName(event.target.value)}
                            className="max-w-xs"
                            autoFocus
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault()
                                saveEdit(group)
                              }
                            }}
                          />
                        ) : (
                          group.name
                        )}
                      </TD>
                      <TD align="right">
                        <div className="flex items-center justify-end gap-1">
                          {isEditing ? (
                            <>
                              <Button
                                type="button"
                                variant="primary"
                                size="sm"
                                onClick={() => saveEdit(group)}
                                disabled={
                                  !editName.trim() || updateGroup.isPending
                                }
                              >
                                {updateGroup.isPending ? (
                                  <Loader2
                                    strokeWidth={1.5}
                                    className="size-4 animate-spin"
                                  />
                                ) : (
                                  <Check strokeWidth={1.5} className="size-4" />
                                )}
                                Save
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setEditingId(null)
                                  setEditName("")
                                }}
                                disabled={updateGroup.isPending}
                              >
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => startEdit(group)}
                              >
                                <Pencil strokeWidth={1.5} className="size-4" />
                                Rename
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => setGroupToDelete(group)}
                              >
                                <Trash2 strokeWidth={1.5} className="size-4" />
                                Delete
                              </Button>
                            </>
                          )}
                        </div>
                      </TD>
                    </TR>
                  )
                })}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>

      <AlertDialog
        open={groupToDelete !== null}
        onOpenChange={(next) => {
          if (!next) setGroupToDelete(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete fund group?</AlertDialogTitle>
            <AlertDialogDescription>
              {groupToDelete ? `"${groupToDelete.name}"` : "This group"} will be
              removed. Groups that still contain funds cannot be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteGroup.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (groupToDelete) {
                  deleteGroup.mutate({
                    params: { path: { fund_group_id: groupToDelete.id } },
                  })
                }
              }}
              disabled={deleteGroup.isPending}
            >
              {deleteGroup.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
