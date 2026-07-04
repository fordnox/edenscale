import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2, LogOut } from "lucide-react"
import { toast } from "sonner"

import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useAuth } from "@edenscale/auth/useAuth"
import { config } from "@edenscale/api/config"

export default function ProfilePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { logout } = useAuth()

  const meQuery = useApiQuery("/users/me", undefined, {
    staleTime: 5 * 60 * 1000,
  })
  const me = meQuery.data

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
    navigate("/manager/login")
  }

  return (
    <>
      <Helmet>
        <title>{`Profile · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Account"
        title="Your profile."
        description="Update your contact details. Your role and organization access live under Organization settings."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
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
