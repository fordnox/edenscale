import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { ArrowUpRight, Loader2, LogOut } from "lucide-react"
import { toast } from "sonner"

import { PageHero } from "@/components/layout/PageHero"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { useAuth } from "@/hooks/useAuth"
import { config } from "@/lib/config"
import { titleCase } from "@/lib/format"
import type { components } from "@/lib/schema"

type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administrator",
  fund_manager: "Fund manager",
  lp: "Limited partner",
}

const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  admin: "Full access to organization settings, audit log, and all firm data.",
  fund_manager: "Manages funds, investors, capital activity, and team members.",
  lp: "Read-only access to your commitments, documents, and letters.",
}

export default function ProfilePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { logout } = useAuth()

  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const me = meQuery.data

  const orgId = me?.organization_id ?? null
  const orgQuery = useApiQuery(
    "/organizations/{organization_id}",
    {
      params: { path: { organization_id: orgId ?? 0 } },
    },
    { enabled: orgId !== null, staleTime: 5 * 60 * 1000 },
  )

  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [phone, setPhone] = useState("")
  const [title, setTitle] = useState("")

  useEffect(() => {
    if (!me) return
    setFirstName(me.first_name ?? "")
    setLastName(me.last_name ?? "")
    setPhone(me.phone ?? "")
    setTitle(me.title ?? "")
  }, [me])

  const updateMe = useApiMutation("patch", "/users/me", {
    onSuccess: () => {
      toast.success("Profile updated")
      queryClient.invalidateQueries({ queryKey: ["/users/me"] })
    },
  })

  const isDirty = useMemo(() => {
    if (!me) return false
    return (
      firstName.trim() !== (me.first_name ?? "") ||
      lastName.trim() !== (me.last_name ?? "") ||
      phone.trim() !== (me.phone ?? "") ||
      title.trim() !== (me.title ?? "")
    )
  }, [me, firstName, lastName, phone, title])

  const canManageOrg = me?.role === "admin" || me?.role === "fund_manager"

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!me || !isDirty || updateMe.isPending) return
    if (!firstName.trim() || !lastName.trim()) {
      toast.error("First and last name are required")
      return
    }
    updateMe.mutate({
      body: {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim() ? phone.trim() : null,
        title: title.trim() ? title.trim() : null,
      },
    })
  }

  function handleReset() {
    if (!me) return
    setFirstName(me.first_name ?? "")
    setLastName(me.last_name ?? "")
    setPhone(me.phone ?? "")
    setTitle(me.title ?? "")
  }

  async function handleSignOut() {
    await logout()
    navigate("/login")
  }

  return (
    <>
      <Helmet>
        <title>{`Profile · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Account"
        title="Your profile."
        description="Update your contact details. Roles and organization membership are managed by your administrator."
      />

      <div className="px-8 pb-16">
        {meQuery.isLoading ? (
          <div className="flex min-h-[280px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : !me ? (
          <Card>
            <CardSection>
              <p className="font-sans text-[14px] text-ink-700">
                Could not load your profile. Try signing in again.
              </p>
            </CardSection>
          </Card>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            <Card>
              <CardSection>
                <Eyebrow>Personal details</Eyebrow>
                <form
                  onSubmit={handleSubmit}
                  className="mt-5 flex flex-col gap-5"
                >
                  <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="profile-first-name">First name</Label>
                      <Input
                        id="profile-first-name"
                        value={firstName}
                        onChange={(event) => setFirstName(event.target.value)}
                        autoComplete="given-name"
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="profile-last-name">Last name</Label>
                      <Input
                        id="profile-last-name"
                        value={lastName}
                        onChange={(event) => setLastName(event.target.value)}
                        autoComplete="family-name"
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="profile-email">Email</Label>
                      <Input
                        id="profile-email"
                        value={me.email}
                        disabled
                        readOnly
                      />
                      <span className="font-sans text-[11px] text-ink-500">
                        Email is managed via your sign-in provider.
                      </span>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="profile-phone">Phone</Label>
                      <Input
                        id="profile-phone"
                        value={phone}
                        onChange={(event) => setPhone(event.target.value)}
                        autoComplete="tel"
                        placeholder="+1 555 555 0123"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5 md:col-span-2">
                      <Label htmlFor="profile-title">Title</Label>
                      <Input
                        id="profile-title"
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                        autoComplete="organization-title"
                        placeholder="e.g. Head of Investor Relations"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 border-t border-[color:var(--border-hairline)] pt-5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleReset}
                      disabled={!isDirty || updateMe.isPending}
                    >
                      Reset
                    </Button>
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={!isDirty || updateMe.isPending}
                    >
                      {updateMe.isPending && (
                        <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                      )}
                      Save changes
                    </Button>
                  </div>
                </form>
              </CardSection>
            </Card>

            <Card>
              <CardSection>
                <Eyebrow>Role &amp; access</Eyebrow>
                <div className="mt-4 flex flex-col gap-3">
                  <div className="flex items-center gap-3">
                    <Badge tone="info">{ROLE_LABELS[me.role]}</Badge>
                    <span className="font-sans text-[12px] text-ink-500">
                      {titleCase(me.role)}
                    </span>
                  </div>
                  <p className="font-sans text-[13px] leading-[1.55] text-ink-700">
                    {ROLE_DESCRIPTIONS[me.role]}
                  </p>
                  <p className="font-sans text-[12px] text-ink-500">
                    Roles are managed by your administrator. Contact them if your
                    access needs to change.
                  </p>
                </div>
              </CardSection>
            </Card>

            <Card>
              <CardSection>
                <Eyebrow>Organization</Eyebrow>
                {orgId === null ? (
                  <p className="mt-4 font-sans text-[13px] text-ink-700">
                    You are not currently associated with an organization.
                  </p>
                ) : (
                  <div className="mt-4 flex flex-col gap-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <h3 className="font-display text-[20px] tracking-tight text-ink-900">
                        {orgQuery.data?.name ?? (orgQuery.isLoading ? "Loading…" : "—")}
                      </h3>
                      {orgQuery.data?.legal_name &&
                        orgQuery.data.legal_name !== orgQuery.data.name && (
                          <span className="font-sans text-[12px] text-ink-500">
                            {orgQuery.data.legal_name}
                          </span>
                        )}
                    </div>
                    {canManageOrg && (
                      <Link
                        to="/settings/organization"
                        className="inline-flex w-fit items-center gap-1 font-sans text-[13px] text-conifer-700 underline-offset-4 hover:underline focus-visible:underline focus-visible:outline-none"
                      >
                        Manage organization settings
                        <ArrowUpRight strokeWidth={1.5} className="size-4" />
                      </Link>
                    )}
                  </div>
                )}
              </CardSection>
            </Card>

            <Card>
              <CardSection>
                <div className="flex items-center justify-between gap-4">
                  <div className="flex flex-col gap-1">
                    <Eyebrow>Session</Eyebrow>
                    <p className="font-sans text-[13px] text-ink-700">
                      Signed in as{" "}
                      <span className="font-medium text-ink-900">{me.email}</span>.
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleSignOut}
                  >
                    <LogOut strokeWidth={1.5} className="size-4" />
                    Sign out
                  </Button>
                </div>
              </CardSection>
            </Card>
          </div>
        )}
      </div>
    </>
  )
}
