import { useEffect, useMemo } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { register } from "@teamhanko/hanko-elements"
import {
  ArrowUpRight,
  Building2,
  FileText,
  LockKeyhole,
} from "lucide-react"
import { BrandMark } from "@edenscale/brand/components/BrandMark"
import { Card, CardSection } from "@edenscale/ui/card"
import { useAuth } from "@edenscale/auth/useAuth"
import { config } from "@edenscale/api/config"
import { hanko } from "@edenscale/auth/hanko"

function safeNextPath(raw: string | null): string {
  if (!raw) return "/investor"
  // Only allow same-origin relative paths; reject protocol-relative and absolute URLs.
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/investor"
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
        <title>{`Investor portal login | ${config.VITE_APP_TITLE}`}</title>
        <meta
          name="description"
          content="Sign in to the NewTaven investor portal."
        />
        <link rel="canonical" href={`${config.VITE_APP_URL}/investor/login`} />
        <meta
          property="og:title"
          content={`Investor portal login | ${config.VITE_APP_TITLE}`}
        />
        <meta
          property="og:description"
          content="Sign in to the NewTaven investor portal."
        />
        <meta property="og:url" content={`${config.VITE_APP_URL}/investor/login`} />
        <meta property="og:type" content="website" />
        <meta
          name="twitter:title"
          content={`Investor portal login | ${config.VITE_APP_TITLE}`}
        />
        <meta
          name="twitter:description"
          content="Sign in to the NewTaven investor portal."
        />
      </Helmet>

      <div className="grid min-h-svh es-paper text-ink-900 lg:grid-cols-[minmax(0,0.95fr)_minmax(480px,1.05fr)]">
        <div className="hidden border-r border-[var(--border-inverse)] bg-conifer-700 text-parchment-50 lg:flex lg:flex-col">
          <div className="flex items-center justify-between border-b border-[var(--border-inverse)] px-10 py-8">
            <div className="flex items-center gap-3">
              <span
                aria-hidden
                className="flex size-9 items-center justify-center border border-[var(--border-inverse)] text-parchment-50"
              >
                <BrandMark className="size-5" />
              </span>
              <span className="font-sans text-[18px] font-semibold tracking-tight">
                {config.VITE_APP_TITLE}
              </span>
            </div>
            <span className="es-eyebrow es-eyebrow-inverse">
              Investor portal
            </span>
          </div>

          <div className="flex flex-1 flex-col justify-between px-10 py-12">
            <div className="max-w-xl">
              <p className="es-eyebrow es-eyebrow-inverse mb-5">
                Limited partner access
              </p>
              <h1 className="font-display text-[48px] font-medium leading-[1.02] text-parchment-50 text-balance xl:text-[60px]">
                Your fund activity, documents, and letters in one secure place.
              </h1>
              <p className="mt-6 max-w-md font-sans text-[16px] leading-[1.65] text-parchment-50/80">
                Review commitments, capital calls, distributions, quarterly
                letters, and shared documents from the NewTaven investor portal.
              </p>
            </div>

            <div className="grid gap-px border border-[var(--border-inverse)] bg-[var(--border-inverse)]">
              <PortalItem
                icon={<Building2 />}
                label="Funds and commitments"
                description="Current exposure and fund-level context."
              />
              <PortalItem
                icon={<ArrowUpRight />}
                label="Capital activity"
                description="Capital calls, distributions, and payment status."
              />
              <PortalItem
                icon={<FileText />}
                label="Documents and letters"
                description="Investor materials organized by date and fund."
              />
            </div>
          </div>
        </div>

        <main className="flex min-h-svh items-center justify-center px-5 py-10 md:px-8">
          <div className="w-full max-w-[440px]">
            <div className="mb-8 lg:hidden">
              <p className="es-eyebrow mb-4">Investor portal</p>
              <h1 className="font-display text-[42px] font-medium leading-[1.02] text-ink-900 text-balance">
                Secure access for limited partners.
              </h1>
            </div>

            <div className="mb-7 hidden lg:block">
              <p className="es-eyebrow mb-4">Investor portal</p>
              <h2 className="font-display text-[44px] font-medium leading-[1.04] text-ink-900">
                Secure access for limited partners.
              </h2>
            </div>

            <Card className="bg-surface">
              <CardSection className="space-y-6">
                <hanko-auth className="block" />
              </CardSection>
            </Card>
          </div>
        </main>
      </div>
    </>
  )
}

interface PortalItemProps {
  icon: React.ReactNode
  label: string
  description: string
}

function PortalItem({ icon, label, description }: PortalItemProps) {
  return (
    <div className="flex gap-4 bg-conifer-700 p-5">
      <span
        aria-hidden
        className="mt-0.5 text-brass-300 [&_svg]:size-5 [&_svg]:stroke-[1.5]"
      >
        {icon}
      </span>
      <div>
        <p className="font-sans text-[14px] font-semibold tracking-tight text-parchment-50">
          {label}
        </p>
        <p className="mt-1 font-sans text-[13px] leading-[1.55] text-parchment-50/70">
          {description}
        </p>
      </div>
    </div>
  )
}
