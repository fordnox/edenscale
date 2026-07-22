import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import {
  Bell,
  Building2,
  ClipboardList,
  Loader2,
  Users,
} from "lucide-react"

import { FundsListCard } from "@/components/dashboard/FundsListCard"
import {
  OnboardingProgressCard,
  type OnboardingStep,
} from "@/components/dashboard/OnboardingProgressCard"
import { BrandMark } from "@edenscale/brand/components/BrandMark"
import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Stat } from "@edenscale/ui/stat"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
import api from "@edenscale/api/client"
import { orgPath } from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency, titleCase } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type DashboardOverview = components["schemas"]["DashboardOverviewResponse"]
type CurrencyTotal = components["schemas"]["CurrencyTotal"]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function mergeCurrencyTotals(
  totals: Map<string, number>,
  entries: CurrencyTotal[],
) {
  for (const { currency_code, amount } of entries) {
    totals.set(
      currency_code,
      (totals.get(currency_code) ?? 0) + parseDecimal(amount),
    )
  }
}

function formatCurrencyTotalMap(totals: Map<string, number>) {
  if (totals.size === 0) return "—"
  return [...totals.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currency, amount]) =>
      formatCurrency(amount, currency, { compact: true }),
    )
    .join(" · ")
}

export default function UserDashboardPage() {
  const navigate = useNavigate()
  const {
    memberships,
    activeOrganizationId,
    setActiveOrganizationId,
  } = useActiveOrganization()
  const { visibleInvitations } = usePendingInvitations()
  const [orgScopeCleared, setOrgScopeCleared] = useState(
    () => activeOrganizationId === null,
  )

  useEffect(() => {
    if (activeOrganizationId !== null) {
      setActiveOrganizationId(null)
      setOrgScopeCleared(true)
      return
    }
    setOrgScopeCleared(true)
  }, [activeOrganizationId, setActiveOrganizationId])

  const dashboardQuery = useQuery({
    queryKey: [
      "user-dashboard",
      memberships.map((membership) => membership.organization_id),
    ],
    enabled: orgScopeCleared && memberships.length > 0,
    queryFn: async () => {
      const results = await Promise.all(
        memberships.map(async (membership) => {
          const { data, error } = await api.GET("/dashboard/overview", {
            headers: { "X-Organization-Id": membership.organization_id },
          })
          if (error) throw error
          return { membership, overview: data }
        }),
      )
      return results
    },
  })

  const organizationOverviews = dashboardQuery.data ?? []
  const totals = useMemo(() => {
    return organizationOverviews.reduce(
      (acc, entry) => {
        const overview = entry.overview as DashboardOverview
        acc.funds += overview.funds_active
        acc.investors += overview.investors_total
        mergeCurrencyTotals(acc.commitments, overview.commitments_by_currency)
        acc.calls += overview.capital_calls_outstanding
        acc.notifications += overview.unread_notifications_count
        acc.tasks += overview.open_tasks_count
        acc.communications += overview.recent_communications.length
        return acc
      },
      {
        funds: 0,
        investors: 0,
        commitments: new Map<string, number>(),
        calls: 0,
        notifications: 0,
        tasks: 0,
        communications: 0,
      },
    )
  }, [organizationOverviews])

  const managerMembership =
    memberships.find((membership) =>
      ["admin", "fund_manager"].includes(membership.role),
    ) ?? memberships[0]
  const managerOrgSlug = managerMembership?.organization.slug ?? ""
  const hasOrganization = memberships.length > 0
  const hasFund = totals.funds > 0
  const hasInvestors = totals.investors > 0
  const hasCommitments = [...totals.commitments.values()].some(
    (amount) => amount > 0,
  )
  const hasCapitalCalls = totals.calls > 0
  const hasCommunications = totals.communications > 0
  const onboardingSteps: OnboardingStep[] = [
    {
      label: "Create organization",
      caption: hasOrganization
        ? `${memberships.length} workspace${memberships.length === 1 ? "" : "s"} attached to your account.`
        : "Create or accept access to a fund manager organization.",
      done: hasOrganization,
      actionLabel: hasOrganization ? "Review organizations" : "Create organization",
      to: hasOrganization ? "/manager" : "/manager/onboarding",
    },
    {
      label: "Create fund",
      caption: "Add the first fund vehicle, vintage year, and reporting currency.",
      done: hasFund,
      actionLabel: "Open funds",
      to: orgPath(managerOrgSlug, "funds"),
    },
    {
      label: "Create investors",
      caption: "Build the limited partner register for the organization.",
      done: hasInvestors,
      actionLabel: "Open investors",
      to: orgPath(managerOrgSlug, "investors"),
    },
    {
      label: "Record commitments",
      caption: "Commitments connect investors to funds and capital activity.",
      done: hasCommitments,
      actionLabel: "Review funds",
      to: orgPath(managerOrgSlug, "funds"),
    },
    {
      label: "Create capital call",
      caption: "Prepare notices once investors and commitments are ready.",
      done: hasCapitalCalls,
      actionLabel: "Open calls",
      to: orgPath(managerOrgSlug, "calls"),
    },
    {
      label: "Send investor update",
      caption: "Draft the first letter or notice for limited partners.",
      done: hasCommunications,
      actionLabel: "Open letters",
      to: orgPath(managerOrgSlug, "letters"),
    },
  ]
  const nextStep = onboardingSteps.find((step) => !step.done)
  const primaryActionPath = nextStep?.to ?? (managerOrgSlug ? orgPath(managerOrgSlug) : "/manager")

  return (
    <>
      <Helmet>
        <title>{`Dashboard · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Account dashboard"
        title="Your workspace overview."
        description="A cross-organization view of setup progress, activity, and the organizations tied to your account."
        actions={
          <>
            {visibleInvitations.length > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate("/manager/invitations/accept")}
              >
                Review invitations
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate(primaryActionPath)}
              disabled={!managerMembership && nextStep?.to !== "/manager/onboarding"}
            >
              {nextStep?.actionLabel ?? "Open workspace"}
            </Button>
          </>
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {dashboardQuery.isLoading && memberships.length > 0 ? (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        ) : (
          <>
            <Card>
              <div className="grid grid-cols-1 gap-0 md:grid-cols-4">
                <CardSection className="border-b border-[color:var(--border-hairline)] md:border-r md:border-b-0">
                  <Stat
                    label="Organizations"
                    value={memberships.length}
                    caption="Workspaces you belong to"
                  />
                </CardSection>
                <CardSection className="border-b border-[color:var(--border-hairline)] md:border-r md:border-b-0">
                  <Stat
                    label="Active funds"
                    value={totals.funds}
                    caption="Across accessible organizations"
                  />
                </CardSection>
                <CardSection className="border-b border-[color:var(--border-hairline)] md:border-r md:border-b-0">
                  <Stat
                    label="Committed capital"
                    value={formatCurrencyTotalMap(totals.commitments)}
                    caption="Visible to your memberships"
                  />
                </CardSection>
                <CardSection>
                  <Stat
                    label="Outstanding calls"
                    value={totals.calls}
                    caption="Scheduled, sent, or overdue"
                  />
                </CardSection>
              </div>
            </Card>

            <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
              {nextStep ? (
                <OnboardingProgressCard
                  steps={onboardingSteps}
                  isStepDisabled={(step) =>
                    !managerMembership &&
                    step.to !== "/manager/onboarding" &&
                    step.to !== "/manager"
                  }
                />
              ) : (
                <FundsListCard
                  funds={organizationOverviews.flatMap((entry) =>
                    (entry.overview as DashboardOverview).recent_funds.map(
                      (fund) => ({
                        fund,
                        to: orgPath(
                          entry.membership.organization.slug,
                          "funds",
                        ),
                      }),
                    ),
                  )}
                />
              )}

              <Card>
                <CardSection className="flex flex-col gap-6">
                  <div className="flex flex-col gap-2">
                    <Eyebrow>Activity</Eyebrow>
                    <h2 className="es-display text-[28px]">Items waiting for you.</h2>
                  </div>
                  <div className="grid grid-cols-1 gap-4">
                    <div className="flex items-center gap-4 border-b border-[color:var(--border-hairline)] pb-4">
                      <Bell strokeWidth={1.5} className="size-5 text-brass-700" />
                      <Stat
                        label="Unread notifications"
                        value={totals.notifications}
                        caption="Across accessible workspaces"
                      />
                    </div>
                    <div className="flex items-center gap-4 border-b border-[color:var(--border-hairline)] pb-4">
                      <ClipboardList strokeWidth={1.5} className="size-5 text-brass-700" />
                      <Stat
                        label="Open tasks"
                        value={totals.tasks}
                        caption="Assigned to your user"
                      />
                    </div>
                    <div className="flex items-center gap-4">
                      <Users strokeWidth={1.5} className="size-5 text-brass-700" />
                      <Stat
                        label="Investor records"
                        value={totals.investors}
                        caption="Visible through your roles"
                      />
                    </div>
                  </div>
                </CardSection>
              </Card>
            </div>

            <div className="mt-8">
              <div className="mb-6 flex items-end justify-between gap-4">
                <div className="flex flex-col gap-2">
                  <Eyebrow>Your organizations</Eyebrow>
                  <h2 className="es-display text-[32px]">
                    Workspaces you belong to.
                  </h2>
                </div>
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => navigate("/manager/onboarding")}
                >
                  Create organization →
                </Button>
              </div>

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                {memberships.map((membership) => {
                  const entry = organizationOverviews.find(
                    (item) =>
                      item.membership.organization_id === membership.organization_id,
                  )
                  const overview = entry?.overview
                  return (
                    <Card key={membership.id}>
                      <CardSection className="flex flex-col gap-5">
                        <div className="flex items-start gap-4">
                          <span className="inline-flex size-11 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
                            <Building2 strokeWidth={1.5} className="size-5" />
                          </span>
                          <div className="flex min-w-0 flex-1 flex-col gap-1">
                            <h3 className="truncate font-display text-[26px] font-medium leading-[1.1] text-ink-900">
                              {membership.organization.name}
                            </h3>
                            <span className="font-sans text-[11px] uppercase tracking-[0.08em] text-ink-500">
                              {titleCase(membership.role)}
                            </span>
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-4 border-t border-[color:var(--border-hairline)] pt-5">
                          <div className="flex flex-col gap-1">
                            <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                              Funds
                            </span>
                            <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                              {overview?.funds_active ?? "—"}
                            </span>
                          </div>
                          <div className="flex flex-col gap-1">
                            <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                              Investors
                            </span>
                            <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                              {overview?.investors_total ?? "—"}
                            </span>
                          </div>
                          <div className="flex flex-col gap-1">
                            <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                              Calls
                            </span>
                            <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                              {overview?.capital_calls_outstanding ?? "—"}
                            </span>
                          </div>
                        </div>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => navigate(orgPath(membership.organization.slug))}
                        >
                          <BrandMark className="size-4" />
                          Open workspace
                        </Button>
                      </CardSection>
                    </Card>
                  )
                })}
              </div>
            </div>

            {dashboardQuery.isError && (
              <Card className="mt-8">
                <CardSection>
                  <Eyebrow>Partial data</Eyebrow>
                  <p className="mt-3 font-sans text-[14px] text-ink-700">
                    Some organization statistics could not be loaded. The
                    organization list is still available.
                  </p>
                </CardSection>
              </Card>
            )}
          </>
        )}
      </div>
    </>
  )
}
