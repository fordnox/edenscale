import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate, useParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { ChevronLeft, Loader2, Pencil, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { PageHero } from "@edenscale/ui/PageHero"
import { CapitalCallCreateDialog } from "@/components/capital-calls/CapitalCallCreateDialog"
import { CapitalCallDetail } from "@/components/capital-calls/CapitalCallDetail"
import { CommitmentCreateDialog } from "@/components/commitments/CommitmentCreateDialog"
import { CommitmentEditDialog } from "@/components/commitments/CommitmentEditDialog"
import { DistributionCreateDialog } from "@/components/distributions/DistributionCreateDialog"
import { DistributionDetail } from "@/components/distributions/DistributionDetail"
import { FundEditDialog } from "@/components/funds/FundEditDialog"
import { FundOverviewTab } from "@/components/funds/FundOverviewTab"
import { FundTeamMemberDialog } from "@/components/funds/FundTeamMemberDialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@edenscale/ui/alert-dialog"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Stat } from "@edenscale/ui/stat"
import { StatusPill } from "@edenscale/ui/StatusPill"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@edenscale/ui/tabs"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useTabParam } from "@/hooks/useTabParam"
import { orgPath } from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"
import {
  formatCurrency,
  formatDate,
  formatPercent,
  titleCase,
} from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type CommitmentRead = components["schemas"]["CommitmentRead"]
type FundTeamMemberRead = components["schemas"]["FundTeamMemberRead"]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

const FUND_DETAIL_TABS = [
  "overview",
  "commitments",
  "calls",
  "distributions",
  "team",
  "letters",
] as const

function memberName(member: FundTeamMemberRead) {
  const name = `${member.user.first_name} ${member.user.last_name}`.trim()
  return name || member.user.email
}

function FundDetailPageContent({ fundId }: { fundId: string }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { activeMembership } = useActiveOrganization()
  const [editOpen, setEditOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [commitmentCreateOpen, setCommitmentCreateOpen] = useState(false)
  const [editingCommitment, setEditingCommitment] =
    useState<CommitmentRead | null>(null)
  const [callCreateOpen, setCallCreateOpen] = useState(false)
  const [distributionCreateOpen, setDistributionCreateOpen] = useState(false)
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)
  const [selectedDistributionId, setSelectedDistributionId] = useState<
    string | null
  >(null)
  const [teamDialogOpen, setTeamDialogOpen] = useState(false)
  const [editingMember, setEditingMember] = useState<FundTeamMemberRead | null>(
    null,
  )
  const [memberToRemove, setMemberToRemove] =
    useState<FundTeamMemberRead | null>(null)
  const [activeTab, setActiveTab] = useTabParam(FUND_DETAIL_TABS, "overview")

  const canManage =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager" ||
    activeMembership?.role === "superadmin"

  const fundQuery = useApiQuery("/funds/{fund_id}", {
    params: { path: { fund_id: fundId } },
  })
  const overviewQuery = useApiQuery("/funds/{fund_id}/overview", {
    params: { path: { fund_id: fundId } },
  })
  const commitmentsQuery = useApiQuery("/funds/{fund_id}/commitments", {
    params: { path: { fund_id: fundId } },
  })
  const callsQuery = useApiQuery("/funds/{fund_id}/capital-calls", {
    params: { path: { fund_id: fundId } },
  })
  const distributionsQuery = useApiQuery("/funds/{fund_id}/distributions", {
    params: { path: { fund_id: fundId } },
  })
  const teamQuery = useApiQuery("/funds/{fund_id}/team", {
    params: { path: { fund_id: fundId } },
  })
  const lettersQuery = useApiQuery("/funds/{fund_id}/communications", {
    params: { path: { fund_id: fundId }, query: { limit: 5 } },
  })

  const archiveFund = useApiMutation("post", "/funds/{fund_id}/archive", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
      toast.success("Fund archived")
      navigate(orgPath(orgSlug ?? "", "funds"))
    },
  })

  const removeMember = useApiMutation(
    "delete",
    "/funds/{fund_id}/team/{member_id}",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: [
            "/funds/{fund_id}/team",
            { params: { path: { fund_id: fundId } } },
          ],
        })
        toast.success("Team member removed")
        setMemberToRemove(null)
      },
    },
  )

  if (fundQuery.isLoading || overviewQuery.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-ink-500">
        <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
      </div>
    )
  }

  if (fundQuery.isError || !fundQuery.data) {
    return (
      <>
        <PageHero
          eyebrow="Programmes"
          title="Fund not found."
          description="We were unable to load this fund. It may have been archived or the link is incorrect."
          actions={
            <Button variant="secondary" size="sm" onClick={() => navigate(orgPath(orgSlug ?? "", "funds"))}>
              <ChevronLeft strokeWidth={1.5} className="size-4" />
              All funds
            </Button>
          }
        />
      </>
    )
  }

  const fund = fundQuery.data
  const overview = overviewQuery.data
  const commitments = commitmentsQuery.data ?? []
  const calls = callsQuery.data ?? []
  const distributions = distributionsQuery.data ?? []
  const team = teamQuery.data ?? []
  const letters = lettersQuery.data ?? []

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

  const canArchive = canManage && fund.status !== "archived"

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
          <>
            <Button variant="ghost" size="sm" onClick={() => navigate(orgPath(orgSlug ?? "", "funds"))}>
              <ChevronLeft strokeWidth={1.5} className="size-4" />
              All funds
            </Button>
            {canManage && (
              <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>
                Edit fund
              </Button>
            )}
            {canArchive && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setArchiveOpen(true)}
              >
                Archive fund
              </Button>
            )}
          </>
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

        {/* KPI strip (global, above tabs) */}
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

        {/* Tabbed sections */}
        <div className="mt-12">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)} className="gap-6">
            <TabsList className="bg-parchment-100">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="commitments">
                Commitments
                <span className="ml-1 text-ink-500">({commitments.length})</span>
              </TabsTrigger>
              <TabsTrigger value="calls">
                Capital calls
                <span className="ml-1 text-ink-500">({calls.length})</span>
              </TabsTrigger>
              <TabsTrigger value="distributions">
                Distributions
                <span className="ml-1 text-ink-500">({distributions.length})</span>
              </TabsTrigger>
              <TabsTrigger value="team">
                Team
                <span className="ml-1 text-ink-500">({team.length})</span>
              </TabsTrigger>
              <TabsTrigger value="letters">
                Letters
                <span className="ml-1 text-ink-500">({letters.length})</span>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <FundOverviewTab
                fund={fund}
                overview={overview}
                calls={calls}
                distributions={distributions}
                commitments={commitments}
              />
            </TabsContent>

            <TabsContent value="commitments">
              {canManage && (
                <div className="mb-3 flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setCommitmentCreateOpen(true)}
                  >
                    New commitment
                  </Button>
                </div>
              )}
              <Card>
                <CardSection className="pt-2 pb-0">
                  {commitmentsQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : commitments.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-8">
                      <Eyebrow>No commitments yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Investor commitments to this fund will appear here once subscriptions are recorded.
                      </p>
                      {canManage && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="mt-2"
                          onClick={() => setCommitmentCreateOpen(true)}
                        >
                          Record a commitment
                        </Button>
                      )}
                    </div>
                  ) : (
                    <DataTable>
                      <thead>
                        <tr>
                          <TH>Investor</TH>
                          <TH align="right">Committed</TH>
                          <TH align="right">Called</TH>
                          <TH align="right">Distributed</TH>
                          <TH align="right">Status</TH>
                          {canManage && <TH align="right">Actions</TH>}
                        </tr>
                      </thead>
                      <tbody>
                        {commitments.map((c) => (
                          <TR key={c.id}>
                            <TD primary>{c.investor.name}</TD>
                            <TD align="right" primary>
                              {formatCurrency(parseDecimal(c.committed_amount), fund.currency_code, {
                                compact: true,
                              })}
                            </TD>
                            <TD align="right">
                              {formatCurrency(parseDecimal(c.called_amount), fund.currency_code, {
                                compact: true,
                              })}
                            </TD>
                            <TD align="right">
                              {formatCurrency(parseDecimal(c.distributed_amount), fund.currency_code, {
                                compact: true,
                              })}
                            </TD>
                            <TD align="right">
                              <StatusPill kind="commitment" value={c.status} />
                            </TD>
                            {canManage && (
                              <TD align="right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setEditingCommitment(c)}
                                >
                                  <Pencil strokeWidth={1.5} className="size-4" />
                                  Edit
                                </Button>
                              </TD>
                            )}
                          </TR>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="calls">
              {canManage && (
                <div className="mb-3 flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setCallCreateOpen(true)}
                  >
                    New capital call
                  </Button>
                </div>
              )}
              <Card>
                <CardSection className="pt-4">
                  {callsQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : calls.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-4">
                      <Eyebrow>No capital calls yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        When you issue a capital call against this fund, it will appear here.
                      </p>
                      {canManage && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="mt-2"
                          onClick={() => setCallCreateOpen(true)}
                        >
                          New capital call
                        </Button>
                      )}
                    </div>
                  ) : (
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {calls.map((c) => (
                        <li
                          key={c.id}
                          className="flex cursor-pointer items-start gap-4 py-4 first:pt-0 last:pb-0"
                          onClick={() => setSelectedCallId(c.id)}
                        >
                          <div className="flex flex-1 flex-col gap-1">
                            <span className="font-sans text-[14px] font-medium text-ink-900">
                              {c.title}
                            </span>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                              <span>Due {formatDate(c.due_date)}</span>
                              <span className="size-1 rounded-full bg-ink-300" />
                              <span className="es-numeric">
                                {formatCurrency(parseDecimal(c.amount), fund.currency_code, {
                                  compact: true,
                                })}
                              </span>
                            </div>
                          </div>
                          <StatusPill kind="capital_call" value={c.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="distributions">
              {canManage && (
                <div className="mb-3 flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setDistributionCreateOpen(true)}
                  >
                    New distribution
                  </Button>
                </div>
              )}
              <Card>
                <CardSection className="pt-4">
                  {distributionsQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : distributions.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-4">
                      <Eyebrow>No distributions yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Distributions issued to limited partners will appear here.
                      </p>
                      {canManage && (
                        <Button
                          variant="secondary"
                          size="sm"
                          className="mt-2"
                          onClick={() => setDistributionCreateOpen(true)}
                        >
                          New distribution
                        </Button>
                      )}
                    </div>
                  ) : (
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {distributions.map((d) => (
                        <li
                          key={d.id}
                          className="flex cursor-pointer items-start gap-4 py-4 first:pt-0 last:pb-0"
                          onClick={() => setSelectedDistributionId(d.id)}
                        >
                          <div className="flex flex-1 flex-col gap-1">
                            <span className="font-sans text-[14px] font-medium text-ink-900">
                              {d.title}
                            </span>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                              <span>{formatDate(d.distribution_date)}</span>
                              <span className="size-1 rounded-full bg-ink-300" />
                              <span className="es-numeric">
                                {formatCurrency(parseDecimal(d.amount), fund.currency_code, {
                                  compact: true,
                                })}
                              </span>
                            </div>
                          </div>
                          <StatusPill kind="distribution" value={d.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="team">
              {canManage && team.length > 0 && (
                <div className="mb-3 flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      setEditingMember(null)
                      setTeamDialogOpen(true)
                    }}
                  >
                    Add team member
                  </Button>
                </div>
              )}
              <Card>
                <CardSection className={team.length > 0 ? "pt-2 pb-0" : undefined}>
                  {teamQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : team.length === 0 ? (
                    <div className="flex flex-col items-start gap-3 py-2">
                      <Eyebrow>No team members assigned</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Assign analysts and partners to this fund to coordinate work.
                      </p>
                      {canManage && (
                        <div className="mt-1 flex flex-wrap items-center gap-4">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              setEditingMember(null)
                              setTeamDialogOpen(true)
                            }}
                          >
                            Add team member
                          </Button>
                          <Link
                            to={orgPath(orgSlug ?? "", "settings")}
                            className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700"
                          >
                            Invite someone to the organization →
                          </Link>
                        </div>
                      )}
                    </div>
                  ) : (
                    <DataTable>
                      <thead>
                        <tr>
                          <TH>Name</TH>
                          <TH>Email</TH>
                          <TH>Title</TH>
                          {canManage && <TH align="right">Actions</TH>}
                        </tr>
                      </thead>
                      <tbody>
                        {team.map((member) => (
                          <TR key={member.id}>
                            <TD primary>{memberName(member)}</TD>
                            <TD>{member.user.email}</TD>
                            <TD>{member.title ?? "—"}</TD>
                            {canManage && (
                              <TD align="right">
                                <div className="flex items-center justify-end gap-1">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                      setEditingMember(member)
                                      setTeamDialogOpen(true)
                                    }}
                                  >
                                    <Pencil strokeWidth={1.5} className="size-4" />
                                    Edit
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setMemberToRemove(member)}
                                  >
                                    <Trash2 strokeWidth={1.5} className="size-4" />
                                    Remove
                                  </Button>
                                </div>
                              </TD>
                            )}
                          </TR>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </CardSection>
              </Card>
            </TabsContent>

            <TabsContent value="letters">
              <Card>
                <CardSection className="pt-4">
                  {lettersQuery.isLoading ? (
                    <div className="flex min-h-[120px] items-center justify-center text-ink-500">
                      <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
                    </div>
                  ) : letters.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 py-4">
                      <Eyebrow>No letters yet</Eyebrow>
                      <p className="font-sans text-[14px] text-ink-700">
                        Quarterly letters and other communications sent against this fund will be listed here.
                      </p>
                      <Link
                        to={orgPath(orgSlug ?? "", "letters")}
                        className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700"
                      >
                        Drafting space →
                      </Link>
                    </div>
                  ) : (
                    <ul className="divide-y divide-[color:var(--border-hairline)]">
                      {letters.map((letter) => (
                        <li
                          key={letter.id}
                          className="flex items-start gap-4 py-4 first:pt-0 last:pb-0"
                        >
                          <div className="flex flex-1 flex-col gap-1">
                            <span className="font-sans text-[14px] font-medium text-ink-900">
                              {letter.subject}
                            </span>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-500">
                              <span>{titleCase(letter.type)}</span>
                              {letter.sent_at && (
                                <>
                                  <span className="size-1 rounded-full bg-ink-300" />
                                  <span>Sent {formatDate(letter.sent_at)}</span>
                                </>
                              )}
                              {letter.recipients.length > 0 && (
                                <>
                                  <span className="size-1 rounded-full bg-ink-300" />
                                  <span>{letter.recipients.length} recipients</span>
                                </>
                              )}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardSection>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <FundEditDialog fund={fund} open={editOpen} onOpenChange={setEditOpen} />

      <CommitmentCreateDialog
        open={commitmentCreateOpen}
        onOpenChange={setCommitmentCreateOpen}
        context={{
          kind: "fund",
          fundId,
          fundName: fund.name,
          existingInvestorIds: commitments.map((c) => c.investor_id),
        }}
      />

      {editingCommitment && (
        <CommitmentEditDialog
          open={editingCommitment !== null}
          onOpenChange={(next) => {
            if (!next) setEditingCommitment(null)
          }}
          commitment={editingCommitment}
          fundId={fundId}
        />
      )}

      <CapitalCallCreateDialog
        open={callCreateOpen}
        onOpenChange={setCallCreateOpen}
        defaultFundId={fundId}
        onCreated={(id) => setSelectedCallId(id)}
      />

      <DistributionCreateDialog
        open={distributionCreateOpen}
        onOpenChange={setDistributionCreateOpen}
        defaultFundId={fundId}
        onCreated={(id) => setSelectedDistributionId(id)}
      />

      <FundTeamMemberDialog
        open={teamDialogOpen}
        onOpenChange={(next) => {
          setTeamDialogOpen(next)
          if (!next) setEditingMember(null)
        }}
        fundId={fundId}
        canManage={canManage}
        member={editingMember}
        existingUserIds={team.map((m) => m.user_id)}
      />

      <Sheet
        open={selectedCallId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedCallId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Capital call detail</SheetTitle>
          <SheetDescription className="sr-only">
            Allocations and actions for the selected capital call.
          </SheetDescription>
          {selectedCallId !== null && (
            <CapitalCallDetail key={selectedCallId} callId={selectedCallId} />
          )}
        </SheetContent>
      </Sheet>

      <Sheet
        open={selectedDistributionId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedDistributionId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Distribution detail</SheetTitle>
          <SheetDescription className="sr-only">
            Allocations and actions for the selected distribution.
          </SheetDescription>
          {selectedDistributionId !== null && (
            <DistributionDetail
              key={selectedDistributionId}
              distributionId={selectedDistributionId}
            />
          )}
        </SheetContent>
      </Sheet>

      <AlertDialog open={archiveOpen} onOpenChange={setArchiveOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive this fund?</AlertDialogTitle>
            <AlertDialogDescription>
              {fund.name} will be marked as archived and hidden from active
              programme views. Existing commitments, calls, and distributions are
              retained. You can still access it directly.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={archiveFund.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                archiveFund.mutate({ params: { path: { fund_id: fundId } } })
              }
              disabled={archiveFund.isPending}
            >
              {archiveFund.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Archive fund
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={memberToRemove !== null}
        onOpenChange={(next) => {
          if (!next) setMemberToRemove(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove team member?</AlertDialogTitle>
            <AlertDialogDescription>
              {memberToRemove ? memberName(memberToRemove) : "This member"} will be
              removed from this fund's roster. This does not affect their
              organization access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={removeMember.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (memberToRemove) {
                  removeMember.mutate({
                    params: {
                      path: { fund_id: fundId, member_id: memberToRemove.id },
                    },
                  })
                }
              }}
              disabled={removeMember.isPending}
            >
              {removeMember.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function FundDetailPage({ fundId }: { fundId: string }) {
  return <FundDetailPageContent fundId={fundId} />
}
