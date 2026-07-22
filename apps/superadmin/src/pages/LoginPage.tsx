import { useEffect, useMemo } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { register } from "@teamhanko/hanko-elements"

import { BrandMark } from "@edenscale/brand/components/BrandMark"
import { Card, CardSection } from "@edenscale/ui/card"
import { useAuth } from "@edenscale/auth/useAuth"
import { config } from "@edenscale/api/config"
import { hanko } from "@edenscale/auth/hanko"

function safeNextPath(raw: string | null): string {
  if (!raw) return "/superadmin"
  // Only allow same-origin relative paths; reject protocol-relative and absolute URLs.
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/superadmin"
  return raw
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { isAuthenticated } = useAuth()

  const nextPath = useMemo(
    () => safeNextPath(searchParams.get("next")),
    [searchParams],
  )

  useEffect(() => {
    register(config.VITE_HANKO_API_URL).catch(console.error)
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      navigate(nextPath, { replace: true })
    }
  }, [isAuthenticated, navigate, nextPath])

  useEffect(() => {
    const unsub = hanko.onSessionCreated(() => {
      navigate(nextPath, { replace: true })
    })
    return () => {
      unsub()
    }
  }, [navigate, nextPath])

  return (
    <>
      <Helmet>
        <title>{`Superadmin login | ${config.VITE_APP_TITLE}`}</title>
        <meta name="robots" content="noindex, nofollow" />
      </Helmet>

      <main className="flex min-h-svh items-center justify-center bg-page px-5 py-10 text-ink-900 md:px-8">
        <div className="w-full max-w-[440px]">
          <div className="mb-8 flex items-center gap-3">
            <span
              aria-hidden
              className="flex size-9 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700"
            >
              <BrandMark className="size-5" />
            </span>
            <span className="font-sans text-[18px] font-semibold tracking-tight">
              {config.VITE_APP_TITLE}
            </span>
          </div>

          <p className="es-eyebrow mb-4">Superadmin console</p>
          <h1 className="mb-7 font-display text-[40px] font-medium leading-[1.04] text-ink-900 text-balance">
            Platform-level access.
          </h1>

          <Card className="bg-surface">
            <CardSection className="space-y-6">
              <hanko-auth className="block" />
            </CardSection>
          </Card>

          <p className="mt-6 font-sans text-[12px] leading-[1.55] text-ink-500">
            This console is reserved for platform superadmins. Fund managers
            and administrators sign in at{" "}
            <a
              href="/manager/login"
              className="text-conifer-700 underline-offset-4 hover:underline"
            >
              /manager
            </a>
            .
          </p>
        </div>
      </main>
    </>
  )
}
