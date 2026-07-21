import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { Building2, ChevronLeft, ChevronRight, Loader2, Plus } from "lucide-react"

import { CreateOrganizationDialog } from "@/components/CreateOrganizationDialog"
import { PageHero } from "@edenscale/ui/PageHero"
import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatDate } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type OrganizationType = components["schemas"]["OrganizationType"]

const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  fund_manager_firm: "Fund manager firm",
  investor_firm: "Investor firm",
  service_provider: "Service provider",
}

// The backend now paginates this route (default limit 100). Page through it
// rather than assuming a complete list — the platform's organization roster
// can outgrow a single page as the business grows.
const PAGE_SIZE = 50

export default function OrganizationsPage() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [page, setPage] = useState(0)

  const orgsQuery = useApiQuery("/superadmin/organizations", {
    params: {
      query: {
        skip: page * PAGE_SIZE,
        // Fetch one extra row so we know whether a next page exists.
        limit: PAGE_SIZE + 1,
      },
    },
  })

  const allOrgs = useMemo(() => orgsQuery.data ?? [], [orgsQuery.data])
  const orgs = useMemo(() => allOrgs.slice(0, PAGE_SIZE), [allOrgs])
  const hasNext = allOrgs.length > PAGE_SIZE

  return (
    <>
      <Helmet>
        <title>{`Organizations · Superadmin · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Superadmin"
        title="Organizations."
        description="Provision and manage every firm on the platform. Create new organizations, assign administrators, and toggle access."
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            <Plus strokeWidth={1.5} className="size-4" />
            Create organization
          </Button>
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          {orgsQuery.isLoading ? (
            <CardSection>
              <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            </CardSection>
          ) : orgs.length === 0 && page === 0 ? (
            <EmptyState
              icon={<Building2 strokeWidth={1.25} />}
              title="No organizations yet"
              body="Create your first organization to onboard a firm."
              action={
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setCreateOpen(true)}
                >
                  <Plus strokeWidth={1.5} className="size-4" />
                  Create organization
                </Button>
              }
            />
          ) : (
            <CardSection>
              <DataTable>
                <thead>
                  <tr>
                    <TH>Name</TH>
                    <TH>Type</TH>
                    <TH>Status</TH>
                    <TH align="right">Members</TH>
                    <TH>Created</TH>
                  </tr>
                </thead>
                <tbody>
                  {orgs.map((org) => (
                    <TR
                      key={org.id}
                      className="cursor-pointer"
                      onClick={() =>
                        navigate(`/superadmin/organizations/${org.id}`)
                      }
                    >
                      <TD primary>{org.name}</TD>
                      <TD>{ORG_TYPE_LABELS[org.type]}</TD>
                      <TD>
                        {org.is_active ? (
                          <Badge tone="active">Active</Badge>
                        ) : (
                          <Badge tone="muted">Disabled</Badge>
                        )}
                      </TD>
                      <TD align="right">{org.member_count}</TD>
                      <TD>
                        {org.created_at ? formatDate(org.created_at) : "—"}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>

              <div className="flex items-center justify-between gap-4 border-t border-[color:var(--border-hairline)] px-6 py-4 md:px-8">
                <p className="font-sans text-[12px] text-ink-500">
                  Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + orgs.length}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={page === 0 || orgsQuery.isFetching}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    <ChevronLeft strokeWidth={1.5} className="size-4" />
                    Previous
                  </Button>
                  <span className="font-sans text-[12px] text-ink-500">
                    Page {page + 1}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={!hasNext || orgsQuery.isFetching}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                    <ChevronRight strokeWidth={1.5} className="size-4" />
                  </Button>
                </div>
              </div>
            </CardSection>
          )}
        </Card>
      </div>

      <CreateOrganizationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
    </>
  )
}
