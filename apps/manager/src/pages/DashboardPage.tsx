import { useQuery } from "@tanstack/react-query"
import {
  ArrowDownToLine,
  Bell,
  Building2,
  ClipboardList,
  Landmark,
  Loader2,
  MailOpen,
  Users,
} from "lucide-react"
import { useNavigate } from "react-router-dom"
import { Helmet } from "react-helmet-async"

import { FundsListCard } from "@/components/dashboard/FundsListCard"
import {
  OnboardingProgressCard,
  type OnboardingStep,
} from "@/components/dashboard/OnboardingProgressCard"

import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { Stat } from "@edenscale/ui/stat"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Button } from "@edenscale/ui/button"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { ProgressBar } from "@edenscale/ui/progress"
import { DataTable, TH, TR, TD } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import api from "@edenscale/api/client"
import { orgPath } from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatRelativeDays,
  titleCase,
} from "@edenscale/shared/format"

const TODAY = new Date()

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { activeMembership, memberships, isSuperadmin } = useActiveOrganization()
  const isLp = !isSuperadmin && activeMembership?.role === "lp"
  const canWriteLetters =
    isSuperadmin ||
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: async () => {
      const { data, error } = await api.GET("/dashboard/overview")
      if (error) throw error
      return data
    },
  })

  const overview = data
  const totalCommitted = parseDecimal(overview?.commitments_total_amount)
  const distributionsYtd = parseDecimal(overview?.distributions_ytd_amount)
  const activeOrgSlug = activeMembership?.organization.slug ?? ""
  const hasFunds = (overview?.funds_active ?? 0) > 0
  const hasInvestors = (overview?.investors_total ?? 0) > 0
  const hasCommitments = totalCommitted > 0
  const hasCapitalCalls =
    (overview?.capital_calls_outstanding ?? 0) > 0 ||
    (overview?.upcoming_capital_calls.length ?? 0) > 0
  const hasCommunications = (overview?.recent_communications.length ?? 0) > 0
  const onboardingSteps: OnboardingStep[] = isLp
    ? [
        {
          label: "Join organization",
          caption: activeMembership?.organization.name ?? "Organization access confirmed",
          done: Boolean(activeMembership),
          actionLabel: "View organizations",
          to: "/manager",
        },
        {
          label: "Review fund access",
          caption: "Confirm the funds tied to your commitments.",
          done: hasFunds,
          actionLabel: "Open funds",
          to: orgPath(activeOrgSlug, "funds"),
        },
        {
          label: "Track capital calls",
          caption: "Open calls appear as soon as they are scheduled or sent.",
          done: hasCapitalCalls,
          actionLabel: "View calls",
          to: orgPath(activeOrgSlug, "calls"),
        },
        {
          label: "Read investor updates",
          caption: "Quarterly letters and notices will be listed here.",
          done: hasCommunications,
          actionLabel: "Open letters",
          to: orgPath(activeOrgSlug, "letters"),
        },
      ]
    : [
        {
          label: "Create organization",
          caption: activeMembership?.organization.name ?? "Organization workspace is ready.",
          done: Boolean(activeMembership),
          actionLabel: "Settings",
          to: orgPath(activeOrgSlug, "settings"),
        },
        {
          label: "Create fund",
          caption: "Add the first vehicle, vintage year, and reporting currency.",
          done: hasFunds,
          actionLabel: "Open funds",
          to: orgPath(activeOrgSlug, "funds"),
        },
        {
          label: "Create investors",
          caption: "Build the limited partner register for this organization.",
          done: hasInvestors,
          actionLabel: "Open investors",
          to: orgPath(activeOrgSlug, "investors"),
        },
        {
          label: "Record commitments",
          caption: "Commitments make called capital and ownership visible.",
          done: hasCommitments,
          actionLabel: "Review funds",
          to: orgPath(activeOrgSlug, "funds"),
        },
        {
          label: "Create capital call",
          caption: "Prepare the first notice once investors and commitments exist.",
          done: hasCapitalCalls,
          actionLabel: "Open calls",
          to: orgPath(activeOrgSlug, "calls"),
        },
        {
          label: "Send investor update",
          caption: "Draft a letter or notice for limited partners.",
          done: hasCommunications,
          actionLabel: "Open letters",
          to: orgPath(activeOrgSlug, "letters"),
        },
      ]
  const nextStep = onboardingSteps.find((step) => !step.done)

  return (
    <>
      <Helmet>
        <title>{`Overview · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow={formatDate(TODAY, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        title="Welcome back."
        description={
          isLp
            ? "A snapshot of your commitments, capital calls, and distributions."
            : "A snapshot of activity across your funds, limited partners, and capital movements."
        }
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => navigate(orgPath(activeOrgSlug, "calls"))}>
              View capital calls
            </Button>
            {canWriteLetters && (
              <Button variant="primary" size="sm" onClick={() => navigate(orgPath(activeOrgSlug, "letters"))}>
                Draft quarterly letter
              </Button>
            )}
          </>
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {isLoading && (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        )}

        {isError && !isLoading && (
          <Card>
            <CardSection>
              <Eyebrow>Could not load overview</Eyebrow>
              <p className="mt-3 font-sans text-[14px] text-ink-700">
                We were unable to fetch your dashboard data. Please refresh, or try again in a moment.
              </p>
            </CardSection>
          </Card>
        )}

        {!isLoading && !isError && overview && (
          <>
            <Card>
              <div className="grid grid-cols-1 gap-0 md:grid-cols-4">
                <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
                  <Stat
                    label={isLp ? "Your funds" : "Active funds"}
                    value={overview.funds_active}
                    caption={
                      isLp
                        ? "Funds you hold a commitment in"
                        : `${overview.investors_total} limited partners`
                    }
                  />
                </CardSection>
                <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
                  <Stat
                    label={isLp ? "Your commitment" : "Total committed"}
                    value={formatCurrency(totalCommitted, "USD", { compact: true })}
                    caption={
                      isLp
                        ? "Across your commitments"
                        : "Across all funds in scope"
                    }
                  />
                </CardSection>
                <CardSection className="md:border-r border-b md:border-b-0 border-[color:var(--border-hairline)]">
                  <Stat
                    label={
                      isLp ? "Open capital calls" : "Capital calls outstanding"
                    }
                    value={overview.capital_calls_outstanding}
                    caption="Scheduled, sent, or overdue"
                  />
                </CardSection>
                <CardSection>
                  <Stat
                    label={
                      isLp ? "Distributions received YTD" : "Distributions YTD"
                    }
                    value={formatCurrency(distributionsYtd, "USD", { compact: true })}
                    caption={`Year ${TODAY.getFullYear()}`}
                  />
                </CardSection>
              </div>
            </Card>

            <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
              {nextStep ? (
                <OnboardingProgressCard steps={onboardingSteps} />
              ) : (
                <FundsListCard
                  funds={overview.recent_funds.map((fund) => ({
                    fund,
                    to: orgPath(activeOrgSlug, "funds"),
                  }))}
                />
              )}

              <Card>
                <CardSection className="flex flex-col gap-6">
                  <div className="flex flex-col gap-2">
                    <Eyebrow>Your organizations</Eyebrow>
                    <h2 className="es-display text-[28px]">Workspaces you belong to.</h2>
                  </div>
                  <div className="flex flex-col border-y border-[color:var(--border-hairline)]">
                    {memberships.map((membership) => {
                      const isActive =
                        membership.organization_id === activeMembership?.organization_id
                      return (
                        <button
                          key={membership.id}
                          type="button"
                          onClick={() => navigate(orgPath(membership.organization.slug))}
                          className="flex min-h-[68px] items-center gap-3 border-b border-[color:var(--border-hairline)] py-4 text-left last:border-b-0"
                        >
                          <span className="inline-flex size-10 shrink-0 items-center justify-center border border-[color:var(--border-hairline)] text-conifer-700">
                            <Building2 strokeWidth={1.5} className="size-4" />
                          </span>
                          <span className="flex min-w-0 flex-1 flex-col gap-1">
                            <span className="truncate font-sans text-[14px] font-semibold text-ink-900">
                              {membership.organization.name}
                            </span>
                            <span className="font-sans text-[11px] uppercase tracking-[0.08em] text-ink-500">
                              {titleCase(membership.role)}
                            </span>
                          </span>
                          {isActive && (
                            <span className="shrink-0 font-sans text-[11px] font-medium text-conifer-700">
                              Active
                            </span>
                          )}
                        </button>
                      )
                    })}
                    {memberships.length === 0 && (
                      <div className="py-6 font-sans text-[14px] text-ink-700">
                        No organization memberships are attached to this account.
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                        Memberships
                      </span>
                      <span className="es-numeric font-display text-[34px] leading-none text-ink-900">
                        {memberships.length}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                        Active role
                      </span>
                      <span className="font-sans text-[15px] font-semibold text-ink-900">
                        {activeMembership ? titleCase(activeMembership.role) : "—"}
                      </span>
                    </div>
                  </div>
                </CardSection>
              </Card>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
              <Card>
                <CardSection className="flex flex-col gap-4">
                  <Bell strokeWidth={1.5} className="size-5 text-brass-700" />
                  <Stat
                    label="Unread notifications"
                    value={overview.unread_notifications_count}
                    caption="Items waiting in your inbox"
                  />
                </CardSection>
              </Card>
              <Card>
                <CardSection className="flex flex-col gap-4">
                  <ClipboardList strokeWidth={1.5} className="size-5 text-brass-700" />
                  <Stat
                    label="Open tasks"
                    value={overview.open_tasks_count}
                    caption={isLp ? "Assigned portal actions" : "Operational follow-ups"}
                  />
                </CardSection>
              </Card>
              <Card>
                <CardSection className="flex flex-col gap-4">
                  <Users strokeWidth={1.5} className="size-5 text-brass-700" />
                  <Stat
                    label={isLp ? "Linked investors" : "Investor records"}
                    value={overview.investors_total}
                    caption={isLp ? "Entities tied to your access" : "Limited partners in scope"}
                  />
                </CardSection>
              </Card>
              <Card>
                <CardSection className="flex flex-col gap-4">
                  {isLp ? (
                    <MailOpen strokeWidth={1.5} className="size-5 text-brass-700" />
                  ) : (
                    <Landmark strokeWidth={1.5} className="size-5 text-brass-700" />
                  )}
                  <Stat
                    label={isLp ? "Recent updates" : "Recent letters"}
                    value={overview.recent_communications.length}
                    caption={isLp ? "Letters and notices" : "Communications in the dashboard feed"}
                  />
                </CardSection>
              </Card>
            </div>

            <div className="mt-8">
              <Card>
                <div className="flex items-end justify-between gap-4 px-6 pt-7 md:px-8 md:pt-8">
                  <div className="flex flex-col gap-2">
                    <Eyebrow>Upcoming</Eyebrow>
                    <h2 className="es-display text-[28px]">
                      Capital calls awaiting attention.
                    </h2>
                  </div>
                  <button
                    type="button"
                    className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700 transition-colors"
                    onClick={() => navigate(orgPath(activeOrgSlug, "calls"))}
                  >
                    Open all →
                  </button>
                </div>
                <CardSection className="pt-5">
                  {overview.upcoming_capital_calls.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-8">
                      <Eyebrow>All clear</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        No outstanding capital calls. New calls will appear here as soon as they are scheduled.
                      </p>
                    </div>
                  ) : (
                    <DataTable>
                      <thead>
                        <tr>
                          <TH>Call</TH>
                          <TH>Fund</TH>
                          <TH align="right">Amount</TH>
                          <TH align="right">Due</TH>
                          <TH align="right">Status</TH>
                        </tr>
                      </thead>
                      <tbody>
                        {overview.upcoming_capital_calls.map((call) => (
                          <TR key={call.id}>
                            <TD primary>
                              <div className="flex items-center gap-3">
                                <span className="inline-flex size-7 shrink-0 items-center justify-center border border-brass-500 text-brass-700">
                                  <ArrowDownToLine strokeWidth={1.5} className="size-3.5" />
                                </span>
                                <span className="leading-tight">{call.title}</span>
                              </div>
                            </TD>
                            <TD>{call.fund_name}</TD>
                            <TD align="right" primary>
                              {formatCurrency(parseDecimal(call.amount), "USD", { compact: true })}
                            </TD>
                            <TD align="right">
                              <div className="flex flex-col items-end leading-tight">
                                <span className="text-ink-900 text-[14px]">
                                  {formatDate(call.due_date)}
                                </span>
                                <span className="text-[11px] text-ink-500">
                                  {formatRelativeDays(call.due_date, TODAY)}
                                </span>
                              </div>
                            </TD>
                            <TD align="right">
                              <StatusPill kind="capital_call" value={call.status} />
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </CardSection>
              </Card>
            </div>

            <div className="mt-12">
              <div className="mb-6 flex items-end justify-between gap-4">
                <div className="flex flex-col gap-2">
                  <Eyebrow>Recent funds</Eyebrow>
                  <h2 className="es-display text-[32px]">
                    Programmes in flight.
                  </h2>
                </div>
                <Button variant="link" size="sm" onClick={() => navigate(orgPath(activeOrgSlug, "funds"))}>
                  All funds →
                </Button>
              </div>

              {overview.recent_funds.length === 0 ? (
                <Card>
                  <CardSection className="flex flex-col gap-2">
                    <Eyebrow>No funds yet</Eyebrow>
                    <p className="font-sans text-[14px] text-ink-700 max-w-xl">
                      Once your organization sets up its first fund, it will appear here with committed and called capital figures.
                    </p>
                  </CardSection>
                </Card>
              ) : (
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {overview.recent_funds.map((fund) => {
                    const committed = parseDecimal(fund.committed_amount)
                    const called = parseDecimal(fund.called_amount)
                    const calledPct = committed > 0 ? called / committed : 0
                    const dpi = parseDecimal(fund.dpi)
                    const irr = parseDecimal(fund.irr)
                    return (
                      <Card key={fund.id} className="flex flex-col">
                        <CardSection className="flex flex-1 flex-col gap-5">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex flex-col gap-1.5">
                              {fund.vintage_year && (
                                <Eyebrow>Vintage {fund.vintage_year}</Eyebrow>
                              )}
                              <h3 className="font-display text-[26px] font-medium leading-[1.1] tracking-[-0.015em] text-ink-900">
                                {fund.name}
                              </h3>
                            </div>
                            <StatusPill kind="fund" value={fund.status} />
                          </div>
                          {fund.strategy && (
                            <p className="font-sans text-[13px] leading-[1.55] text-ink-500">
                              {fund.strategy}
                            </p>
                          )}
                          <div className="grid grid-cols-3 gap-4 border-t border-[color:var(--border-hairline)] pt-5">
                            <div className="flex flex-col gap-1">
                              <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                                Committed
                              </span>
                              <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                                {formatCurrency(committed, fund.currency_code, { compact: true })}
                              </span>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                                DPI
                              </span>
                              <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                                {fund.dpi ? `${dpi.toFixed(2)}x` : "—"}
                              </span>
                            </div>
                            <div className="flex flex-col gap-1">
                              <span className="font-sans text-[10px] uppercase tracking-[0.12em] text-ink-500">
                                Net IRR
                              </span>
                              <span className="es-numeric font-sans text-[15px] font-semibold text-ink-900">
                                {fund.irr ? formatPercent(irr) : "—"}
                              </span>
                            </div>
                          </div>
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between text-[11px] text-ink-500">
                              <span>Capital called</span>
                              <span className="es-numeric">
                                {formatPercent(calledPct)}
                              </span>
                            </div>
                            <ProgressBar value={calledPct} />
                          </div>
                        </CardSection>
                      </Card>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
