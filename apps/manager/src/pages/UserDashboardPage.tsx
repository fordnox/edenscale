import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import {
  ArrowDownToLine,
  Bell,
  Building2,
  CheckCircle2,
  Circle,
  ClipboardList,
  Landmark,
  Loader2,
  Users,
} from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { Stat } from "@edenscale/ui/stat"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { usePendingInvitations } from "@edenscale/shared/hooks/usePendingInvitations"
import api from "@edenscale/api/client"
import { orgPath } from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatPercent, titleCase } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type DashboardOverview = components["schemas"]["DashboardOverviewResponse"]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function StepStatusIcon({ done }: { done: boolean }) {
  const Icon = done ? CheckCircle2 : Circle
  return (
    <Icon
      aria-hidden
      strokeWidth={1.5}
      className={done ? "size-5 text-conifer-700" : "size-5 text-ink-400"}
    />
  )
}

export default function UserDashboardPage() {
  const navigate = useNavigate()
  const {
    memberships,
    activeOrganizationId,
    setActiveOrganizationId,
    isSuperadmin,
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
        acc.commitments += parseDecimal(overview.commitments_total_amount)
        acc.calls += overview.capital_calls_outstanding
        acc.notifications += overview.unread_notifications_count
        acc.tasks += overview.open_tasks_count
        acc.communications += overview.recent_communications.length
        return acc
      },
      {
        funds: 0,
        investors: 0,
        commitments: 0,
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
  const hasFirm = memberships.length > 0
  const hasFund = totals.funds > 0
  const hasInvestors = totals.investors > 0
  const hasCommitments = totals.commitments > 0
  const hasCapitalCalls = totals.calls > 0
  const hasCommunications = totals.communications > 0
  const onboardingSteps = [
    {
      label: "Create firm",
      caption: hasFirm
        ? `${memberships.length} workspace${memberships.length === 1 ? "" : "s"} attached to your account.`
        : "Create or accept access to a fund manager firm.",
      done: hasFirm,
      actionLabel: hasFirm ? "Review organizations" : "Create firm",
      to: hasFirm ? "/manager" : "/manager/onboarding",
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
      caption: "Build the limited partner register for the firm.",
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
  const completedSteps = onboardingSteps.filter((step) => step.done).length
  const onboardingProgress = completedSteps / onboardingSteps.length
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
        description="A cross-organization view of setup progress, activity, and the firms tied to your account."
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
                    caption={
                      isSuperadmin
                        ? "Tenant memberships for this account"
                        : "Workspaces you belong to"
                    }
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
                    value={formatCurrency(totals.commitments, "USD", {
                      compact: true,
                    })}
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
              <Card>
                <div className="flex flex-col gap-5 px-6 pt-7 md:px-8 md:pt-8">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="flex flex-col gap-2">
                      <Eyebrow>Onboarding progress</Eyebrow>
                      <h2 className="es-display text-[28px]">
                        {nextStep
                          ? `${nextStep.label} is next.`
                          : "Core setup is complete."}
                      </h2>
                      <p className="max-w-2xl font-sans text-[14px] leading-[1.6] text-ink-700">
                        {nextStep
                          ? nextStep.caption
                          : "Your account has the main operating pieces in place across the organizations you can access."}
                      </p>
                    </div>
                    <Button
                      variant={nextStep ? "primary" : "secondary"}
                      size="sm"
                      onClick={() => navigate(primaryActionPath)}
                      disabled={!managerMembership && nextStep?.to !== "/manager/onboarding"}
                    >
                      {nextStep ? nextStep.actionLabel : "Review organizations"}
                    </Button>
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between font-sans text-[12px] text-ink-500">
                      <span>
                        {completedSteps} of {onboardingSteps.length} complete
                      </span>
                      <span className="es-numeric">
                        {formatPercent(onboardingProgress, 0)}
                      </span>
                    </div>
                    <ProgressBar value={onboardingProgress} tone="brass" />
                  </div>
                </div>

                <CardSection className="pt-6">
                  <div className="grid grid-cols-1 gap-0 border border-[color:var(--border-hairline)] md:grid-cols-2">
                    {onboardingSteps.map((step, index) => (
                      <button
                        key={step.label}
                        type="button"
                        onClick={() => navigate(step.to)}
                        disabled={!managerMembership && step.to !== "/manager/onboarding" && step.to !== "/manager"}
                        className="group flex min-h-[112px] items-start gap-4 border-b border-[color:var(--border-hairline)] p-5 text-left transition-colors duration-[140ms] hover:bg-parchment-100 disabled:cursor-not-allowed disabled:opacity-60 md:[&:nth-child(odd)]:border-r md:[&:nth-last-child(-n+2)]:border-b-0"
                      >
                        <StepStatusIcon done={step.done} />
                        <span className="flex min-w-0 flex-1 flex-col gap-1">
                          <span className="font-sans text-[14px] font-semibold text-ink-900">
                            {index + 1}. {step.label}
                          </span>
                          <span className="font-sans text-[13px] leading-[1.5] text-ink-500">
                            {step.caption}
                          </span>
                          <span className="mt-1 font-sans text-[12px] font-medium text-conifer-700 group-hover:border-b group-hover:border-brass-500">
                            {step.done ? "Review" : step.actionLabel}
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                </CardSection>
              </Card>

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
                  Create firm →
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
                          <Landmark strokeWidth={1.5} />
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
