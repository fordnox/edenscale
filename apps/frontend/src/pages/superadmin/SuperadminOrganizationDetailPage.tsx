import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { ChevronLeft, Loader2, Plus, Users } from "lucide-react"
import { toast } from "sonner"

import { RequireSuperadmin } from "@/components/RequireSuperadmin"
import { AssignAdminDialog } from "@/components/superadmin/AssignAdminDialog"
import { PageHero } from "@/components/layout/PageHero"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Eyebrow } from "@/components/ui/eyebrow"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatDate } from "@/lib/format"
import type { components } from "@/lib/schema"

type UserRole = components["schemas"]["UserRole"]
type OrganizationType = components["schemas"]["OrganizationType"]

const ROLE_LABELS: Record<UserRole, string> = {
  superadmin: "Superadmin",
  admin: "Administrator",
  fund_manager: "Fund manager",
  lp: "Limited partner",
}

const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  fund_manager_firm: "Fund manager firm",
  investor_firm: "Investor firm",
  service_provider: "Service provider",
}

export default function SuperadminOrganizationDetailPage() {
  return (
    <RequireSuperadmin>
      <SuperadminOrganizationDetailContent />
    </RequireSuperadmin>
  )
}

function SuperadminOrganizationDetailContent() {
  const params = useParams<{ organizationId: string }>()
  const orgId = params.organizationId ? Number(params.organizationId) : NaN

  if (!Number.isFinite(orgId)) {
    return (
      <div className="px-8 py-16">
        <Card>
          <EmptyState
            title="Organization not found"
            body="The URL does not include a valid organization id."
            action={
              <Button asChild variant="secondary" size="sm">
                <Link to="/superadmin/organizations">Back to organizations</Link>
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  return <OrganizationDetail organizationId={orgId} />
}

interface OrganizationDetailProps {
  organizationId: number
}

function OrganizationDetail({ organizationId }: OrganizationDetailProps) {
  const queryClient = useQueryClient()
  const [assignOpen, setAssignOpen] = useState(false)

  const orgQuery = useApiQuery("/organizations/{organization_id}", {
    params: { path: { organization_id: organizationId } },
  })
  const membersQuery = useApiQuery(
    "/superadmin/organizations/{organization_id}/members",
    { params: { path: { organization_id: organizationId } } },
  )

  const org = orgQuery.data
  const members = useMemo(() => membersQuery.data ?? [], [membersQuery.data])

  const disableMutation = useApiMutation(
    "patch",
    "/superadmin/organizations/{organization_id}/disable",
    {
      onSuccess: () => {
        toast.success("Organization disabled")
        queryClient.invalidateQueries({
          queryKey: ["/organizations/{organization_id}"],
        })
        queryClient.invalidateQueries({
          queryKey: ["/superadmin/organizations"],
        })
      },
    },
  )

  const enableMutation = useApiMutation(
    "patch",
    "/superadmin/organizations/{organization_id}/enable",
    {
      onSuccess: () => {
        toast.success("Organization enabled")
        queryClient.invalidateQueries({
          queryKey: ["/organizations/{organization_id}"],
        })
        queryClient.invalidateQueries({
          queryKey: ["/superadmin/organizations"],
        })
      },
    },
  )

  function handleToggleActive() {
    if (!org) return
    const args = { params: { path: { organization_id: org.id } } }
    if (org.is_active) {
      disableMutation.mutate(args)
    } else {
      enableMutation.mutate(args)
    }
  }

  const isToggling = disableMutation.isPending || enableMutation.isPending

  const existingUsers = useMemo(
    () => members.map((m) => m.user),
    [members],
  )

  return (
    <>
      <Helmet>
        <title>
          {`${org?.name ?? "Organization"} · Superadmin · ${config.VITE_APP_TITLE}`}
        </title>
      </Helmet>

      <div className="px-8 pt-6">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/superadmin/organizations">
            <ChevronLeft strokeWidth={1.5} className="size-4" />
            All organizations
          </Link>
        </Button>
      </div>

      <PageHero
        eyebrow="Superadmin · Organization"
        title={org ? `${org.name}.` : "Organization."}
        description="Inspect firm metadata, manage administrators, and toggle access."
        actions={
          org ? (
            <Button
              variant={org.is_active ? "secondary" : "primary"}
              size="sm"
              onClick={handleToggleActive}
              disabled={isToggling}
            >
              {isToggling && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              {org.is_active ? "Disable organization" : "Enable organization"}
            </Button>
          ) : undefined
        }
      />

      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-8 pb-16">
        {orgQuery.isLoading ? (
          <Card>
            <CardSection>
              <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            </CardSection>
          </Card>
        ) : !org ? (
          <Card>
            <EmptyState
              title="Organization not found"
              body="This organization may have been removed."
              action={
                <Button asChild variant="secondary" size="sm">
                  <Link to="/superadmin/organizations">
                    Back to organizations
                  </Link>
                </Button>
              }
            />
          </Card>
        ) : (
          <>
            <Card>
              <CardSection>
                <div className="flex items-baseline justify-between gap-3">
                  <Eyebrow>Firm details</Eyebrow>
                  <div className="flex items-center gap-2">
                    <Badge tone="muted">{ORG_TYPE_LABELS[org.type]}</Badge>
                    {org.is_active ? (
                      <Badge tone="active">Active</Badge>
                    ) : (
                      <Badge tone="negative">Disabled</Badge>
                    )}
                  </div>
                </div>
                <dl className="mt-5 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
                  <DetailRow label="Name" value={org.name} />
                  <DetailRow label="Legal name" value={org.legal_name} />
                  <DetailRow label="Tax ID" value={org.tax_id} />
                  <DetailRow label="Website" value={org.website} />
                  <DetailRow
                    label="Created"
                    value={
                      org.created_at ? formatDate(org.created_at) : null
                    }
                  />
                  <DetailRow label="Description" value={org.description} />
                </dl>
              </CardSection>
            </Card>

            <Card>
              <div className="flex items-end justify-between gap-4 px-6 pt-6 md:px-8 md:pt-8">
                <div className="flex flex-col gap-1.5">
                  <Eyebrow>Members</Eyebrow>
                  <p className="font-sans text-[13px] text-ink-700">
                    Promote an existing member or invite a new admin by email.
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setAssignOpen(true)}
                >
                  <Plus strokeWidth={1.5} className="size-4" />
                  Assign admin
                </Button>
              </div>
              <CardSection className="pt-4">
                {membersQuery.isLoading ? (
                  <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                    <Loader2
                      strokeWidth={1.5}
                      className="size-6 animate-spin"
                    />
                  </div>
                ) : members.length === 0 ? (
                  <EmptyState
                    icon={<Users strokeWidth={1.25} />}
                    title="No members yet"
                    body="Assign the first administrator to get this organization started."
                  />
                ) : (
                  <DataTable>
                    <thead>
                      <tr>
                        <TH>Name</TH>
                        <TH>Email</TH>
                        <TH>Role</TH>
                        <TH>Status</TH>
                      </tr>
                    </thead>
                    <tbody>
                      {members.map((m) => {
                        const name =
                          `${m.user.first_name} ${m.user.last_name}`.trim() ||
                          m.user.email
                        return (
                          <TR key={m.id}>
                            <TD primary>{name}</TD>
                            <TD>{m.user.email}</TD>
                            <TD>
                              <Badge tone="info">{ROLE_LABELS[m.role]}</Badge>
                            </TD>
                            <TD>
                              {m.user.is_active ? (
                                <Badge tone="active">Active</Badge>
                              ) : (
                                <Badge tone="muted">Inactive</Badge>
                              )}
                            </TD>
                          </TR>
                        )
                      })}
                    </tbody>
                  </DataTable>
                )}
              </CardSection>
            </Card>
          </>
        )}
      </div>

      <AssignAdminDialog
        open={assignOpen}
        onOpenChange={setAssignOpen}
        organizationId={organizationId}
        existingUsers={existingUsers}
      />
    </>
  )
}

function DetailRow({
  label,
  value,
}: {
  label: string
  value: string | null | undefined
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="font-sans text-[11px] tracking-[0.06em] uppercase text-ink-500">
        {label}
      </dt>
      <dd className="font-sans text-[14px] text-ink-900 break-words">
        {value && value.trim() ? value : "—"}
      </dd>
    </div>
  )
}
