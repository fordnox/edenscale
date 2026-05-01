import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2, Plus, Users } from "lucide-react"
import { toast } from "sonner"

import { RequireRole } from "@/components/RequireRole"
import { PageHero } from "@/components/layout/PageHero"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/EmptyState"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import type { components } from "@/lib/schema"

type UserRole = components["schemas"]["UserRole"]
type UserRead = components["schemas"]["UserRead"]
type OrganizationType = components["schemas"]["OrganizationType"]

const ROLE_LABELS: Record<UserRole, string> = {
  superadmin: "Superadmin",
  admin: "Administrator",
  fund_manager: "Fund manager",
  lp: "Limited partner",
}

const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  fund_manager_firm: "Fund manager firm",
  investor_firm: "Investor firm",
  service_provider: "Service provider",
}

function fullName(user: UserRead) {
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

  const orgQuery = useApiQuery(
    "/organizations/{organization_id}",
    { params: { path: { organization_id: orgId ?? 0 } } },
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

  function handleRoleChange(user: UserRead, nextRole: UserRole) {
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

  return (
    <>
      <Helmet>
        <title>{`Organization · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Settings"
        title="Organization."
        description="Update firm details and manage who has access. Changes apply across the workspace."
      />

      <div className="px-8 pb-16">
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
                <div className="flex items-baseline justify-between gap-3">
                  <Eyebrow>Firm details</Eyebrow>
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
                    body="Invite the first member of your firm to get started."
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
          </div>
        )}
      </div>

      <InviteUserDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        defaultOrganizationId={orgId}
        canChooseOrganization={isAdmin}
      />
    </>
  )
}

interface InviteUserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultOrganizationId: number | null
  canChooseOrganization: boolean
}

function InviteUserDialog({
  open,
  onOpenChange,
  defaultOrganizationId,
  canChooseOrganization,
}: InviteUserDialogProps) {
  const queryClient = useQueryClient()

  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [phone, setPhone] = useState("")
  const [title, setTitle] = useState("")
  const [role, setRole] = useState<UserRole>("fund_manager")
  const [organizationId, setOrganizationId] = useState<string>(
    defaultOrganizationId !== null ? String(defaultOrganizationId) : "none",
  )

  const orgsQuery = useApiQuery("/organizations", undefined, {
    enabled: open && canChooseOrganization,
  })

  const inviteUser = useApiMutation("post", "/users", {
    onSuccess: () => {
      toast.success("User invited")
      queryClient.invalidateQueries({ queryKey: ["/users"] })
      reset()
      onOpenChange(false)
    },
  })

  function reset() {
    setFirstName("")
    setLastName("")
    setEmail("")
    setPhone("")
    setTitle("")
    setRole("fund_manager")
    setOrganizationId(
      defaultOrganizationId !== null ? String(defaultOrganizationId) : "none",
    )
  }

  function handleOpenChange(next: boolean) {
    if (!next && inviteUser.isPending) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inviteUser.isPending) return
    if (!firstName.trim() || !lastName.trim() || !email.trim()) {
      toast.error("First name, last name, and email are required")
      return
    }

    const orgIdValue =
      canChooseOrganization && organizationId !== "none"
        ? Number(organizationId)
        : defaultOrganizationId

    inviteUser.mutate({
      body: {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone: phone.trim() ? phone.trim() : null,
        title: title.trim() ? title.trim() : null,
        role,
        organization_id: orgIdValue ?? null,
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Invite user
          </DialogTitle>
          <DialogDescription>
            The invited user will be able to claim the account by signing in
            with this email through the configured identity provider.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-first-name">First name</Label>
              <Input
                id="invite-first-name"
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-last-name">Last name</Label>
              <Input
                id="invite-last-name"
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                required
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-phone">Phone (optional)</Label>
              <Input
                id="invite-phone"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                autoComplete="tel"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-title">Title (optional)</Label>
              <Input
                id="invite-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Head of Investor Relations"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="invite-role">Role</Label>
              <Select
                value={role}
                onValueChange={(value) => setRole(value as UserRole)}
              >
                <SelectTrigger id="invite-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(["admin", "fund_manager", "lp"] as const).map((value) => (
                    <SelectItem key={value} value={value}>
                      {ROLE_LABELS[value]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {canChooseOrganization && (
              <div className="flex flex-col gap-2">
                <Label htmlFor="invite-org">Organization</Label>
                <Select
                  value={organizationId}
                  onValueChange={setOrganizationId}
                >
                  <SelectTrigger id="invite-org" className="w-full">
                    <SelectValue placeholder="No organization" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No organization</SelectItem>
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
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={inviteUser.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={
                inviteUser.isPending ||
                !firstName.trim() ||
                !lastName.trim() ||
                !email.trim()
              }
            >
              {inviteUser.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Send invite
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
