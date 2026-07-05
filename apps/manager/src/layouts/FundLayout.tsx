import { Helmet } from "react-helmet-async"
import {
  Navigate,
  Outlet,
  useNavigate,
  useOutletContext,
  useParams,
  useSearchParams,
} from "react-router-dom"
import { ChevronLeft, Loader2 } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import {
  FUND_SECTIONS,
  fundPath,
  fundSectionPath,
  orgPath,
  type FundSection,
} from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatPercent } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type FundRead = components["schemas"]["FundRead"]

export interface FundOutletContext {
  fund: FundRead
  canManage: boolean
}

/** Fund resolved by FundLayout, available to the fund section pages below it. */
export function useFundContext(): FundOutletContext {
  return useOutletContext<FundOutletContext>()
}

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function FundNotFound({ orgSlug }: { orgSlug: string }) {
  const navigate = useNavigate()
  return (
    <PageHero
      eyebrow="Programmes"
      title="Fund not found."
      description="We were unable to load this fund. It may have been archived or the link is incorrect."
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(orgPath(orgSlug, "funds"))}
        >
          <ChevronLeft strokeWidth={1.5} className="size-4" />
          All funds
        </Button>
      }
    />
  )
}

function FundShell({ fund }: { fund: FundRead }) {
  const navigate = useNavigate()
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { activeMembership } = useActiveOrganization()

  const canManage =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager" ||
    activeMembership?.role === "superadmin"

  const overviewQuery = useApiQuery("/funds/{fund_id}/overview", {
    params: { path: { fund_id: fund.id } },
  })
  const commitmentsQuery = useApiQuery("/funds/{fund_id}/commitments", {
    params: { path: { fund_id: fund.id } },
  })

  if (overviewQuery.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  const overview = overviewQuery.data
  const commitments = commitmentsQuery.data ?? []

  const committed = parseDecimal(overview?.committed)
  const called = parseDecimal(overview?.called)
  const distributed = parseDecimal(overview?.distributed)
  const remaining = parseDecimal(overview?.remaining_commitment)
  const calledPct = committed > 0 ? called / committed : 0
  const targetSize = parseDecimal(fund.target_size)
  const targetPct = targetSize > 0 ? Math.min(committed / targetSize, 1) : 0
  const eyebrowParts = [
    fund.vintage_year ? `Vintage ${fund.vintage_year}` : null,
    fund.currency_code,
  ].filter((part): part is string => Boolean(part))

  return (
    <>
      <Helmet>
        <title>{`${fund.name} · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>

      <PageHero
        eyebrow={eyebrowParts.join(" · ")}
        title={fund.name}
        description={fund.description ?? undefined}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(orgPath(orgSlug ?? "", "funds"))}
          >
            <ChevronLeft strokeWidth={1.5} className="size-4" />
            All funds
          </Button>
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <StatusPill kind="fund" value={fund.status} />
          {fund.legal_name && (
            <span className="font-sans text-[13px] text-ink-500">
              {fund.legal_name}
            </span>
          )}
          {fund.strategy && (
            <span className="font-sans text-[13px] text-ink-500">
              {fund.strategy}
            </span>
          )}
        </div>

        {/* KPI strip (global, shown on every fund section page) */}
        <Card className="mt-6">
          <div className="grid grid-cols-2 md:grid-cols-4">
            <CardSection className="border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Committed"
                value={formatCurrency(committed, fund.currency_code, { compact: true })}
                caption={
                  targetSize > 0
                    ? `${formatPercent(targetPct)} of ${formatCurrency(targetSize, fund.currency_code, { compact: true })} target`
                    : `${commitments.length} commitments`
                }
              />
            </CardSection>
            <CardSection className="border-b md:border-r md:border-b-0 border-[color:var(--border-hairline)]">
              <Stat
                label="Called"
                value={formatCurrency(called, fund.currency_code, { compact: true })}
                caption={
                  committed > 0 ? `${formatPercent(calledPct)} of commitment` : "—"
                }
              />
            </CardSection>
            <CardSection className="border-r border-[color:var(--border-hairline)]">
              <Stat
                label="Distributed"
                value={formatCurrency(distributed, fund.currency_code, { compact: true })}
                caption="Lifetime"
              />
            </CardSection>
            <CardSection>
              <Stat
                label="Remaining"
                value={formatCurrency(remaining, fund.currency_code, { compact: true })}
                caption="Uncalled commitment"
              />
            </CardSection>
          </div>
        </Card>

        <div className="mt-12">
          <Outlet context={{ fund, canManage } satisfies FundOutletContext} />
        </div>
      </div>
    </>
  )
}

// Fund workspace: resolves the :fundSlug param to a fund, renders the shared
// fund chrome (hero, status line, KPI strip), and mounts the active section
// page in an Outlet. Rendered inside OrgLayout's shell, so an org is already
// active.
export default function FundLayout() {
  const { orgSlug, fundSlug } = useParams<{
    orgSlug: string
    fundSlug: string
  }>()
  const [searchParams] = useSearchParams()
  // Resolve the fund directly by slug (O(1) on the backend) rather than
  // scanning the paginated /funds list, which would miss funds past the
  // default page size.
  const fundQuery = useApiQuery(
    "/funds/by-slug/{slug}",
    { params: { path: { slug: fundSlug ?? "" } } },
    { enabled: Boolean(fundSlug), retry: false },
  )

  // Fund sections used to be ?tab= values on a single detail page — keep old
  // links working by redirecting to the section route.
  const legacyTab = searchParams.get("tab")
  if (orgSlug && fundSlug && legacyTab) {
    if ((FUND_SECTIONS as readonly string[]).includes(legacyTab)) {
      return (
        <Navigate
          to={fundSectionPath(orgSlug, fundSlug, legacyTab as FundSection)}
          replace
        />
      )
    }
    return <Navigate to={fundPath(orgSlug, fundSlug)} replace />
  }

  if (fundQuery.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  const fund = fundQuery.data

  if (!fund) {
    return <FundNotFound orgSlug={orgSlug ?? ""} />
  }

  return <FundShell fund={fund} />
}
