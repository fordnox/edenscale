import { useEffect, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { AlertCircle, ArrowLeft, Loader2, MailCheck } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useAuth } from "@/hooks/useAuth"
import { config } from "@/lib/config"

export default function InvitationAcceptPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  const queryClient = useQueryClient()

  const { isAuthenticated, isLoading: authLoading } = useAuth()
  const { setActiveOrganizationId } = useActiveOrganization()

  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (authLoading || isAuthenticated) return
    const next = `/invitations/accept${
      token ? `?token=${encodeURIComponent(token)}` : ""
    }`
    navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true })
  }, [authLoading, isAuthenticated, navigate, token])

  const acceptMutation = useApiMutation("post", "/invitations/accept", {
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/users/me/memberships"] })
      queryClient.invalidateQueries({ queryKey: ["/users/me"] })
      setActiveOrganizationId(data.organization_id)
      toast.success(`Welcome to ${data.organization.name}.`)
      navigate("/")
    },
    onError: (error) => {
      const detail = (error as { detail?: unknown } | null)?.detail
      setErrorMessage(
        typeof detail === "string"
          ? detail
          : "We couldn't accept this invitation. The link may be expired or revoked.",
      )
    },
  })

  function handleAccept() {
    if (!token || acceptMutation.isPending) return
    setErrorMessage(null)
    acceptMutation.mutate({ body: { token } })
  }

  if (authLoading || !isAuthenticated) {
    return (
      <Frame title="Accept invitation">
        <div className="flex min-h-[160px] items-center justify-center text-ink-500">
          <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
        </div>
      </Frame>
    )
  }

  if (!token) {
    return (
      <Frame title="Accept invitation">
        <Card>
          <EmptyState
            icon={<AlertCircle strokeWidth={1.25} />}
            title="No invitation token"
            body="This link looks malformed. Please open the most recent invitation email from your administrator."
            action={
              <Button asChild variant="secondary" size="sm">
                <Link to="/">
                  <ArrowLeft strokeWidth={1.5} className="size-4" />
                  Back to home
                </Link>
              </Button>
            }
          />
        </Card>
      </Frame>
    )
  }

  if (errorMessage) {
    return (
      <Frame title="Accept invitation">
        <Card>
          <EmptyState
            icon={<AlertCircle strokeWidth={1.25} />}
            title="We couldn't accept this invitation"
            body={errorMessage}
            action={
              <Button asChild variant="secondary" size="sm">
                <Link to="/">
                  <ArrowLeft strokeWidth={1.5} className="size-4" />
                  Back to home
                </Link>
              </Button>
            }
          />
        </Card>
      </Frame>
    )
  }

  return (
    <Frame title="Accept invitation">
      <Card>
        <CardSection>
          <div className="flex flex-col items-center gap-4 text-center">
            <span
              aria-hidden
              className="text-[color:var(--brass-700)] [&_svg]:size-8 [&_svg]:stroke-[1.25]"
            >
              <MailCheck />
            </span>
            <h1 className="font-display text-[28px] leading-[1.1] font-medium tracking-[-0.015em] text-ink-900">
              You're being invited to join an organization.
            </h1>
            <p className="max-w-md font-sans text-[14px] leading-[1.6] text-ink-700">
              Accept this invitation to add the organization to your account.
              You'll be able to switch between organizations from the top bar.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={handleAccept}
                disabled={acceptMutation.isPending}
              >
                {acceptMutation.isPending && (
                  <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                )}
                Accept invitation
              </Button>
              <Button asChild variant="ghost" size="md">
                <Link to="/">Not now</Link>
              </Button>
            </div>
          </div>
        </CardSection>
      </Card>
    </Frame>
  )
}

interface FrameProps {
  title: string
  children: React.ReactNode
}

function Frame({ title, children }: FrameProps) {
  return (
    <>
      <Helmet>
        <title>{`${title} · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <div className="flex min-h-svh items-center justify-center bg-page p-6">
        <div className="w-full max-w-lg">{children}</div>
      </div>
    </>
  )
}
