import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { Building2, Loader2, Plus } from "lucide-react"

import { RequireSuperadmin } from "@/components/RequireSuperadmin"
import { CreateOrganizationDialog } from "@/components/superadmin/CreateOrganizationDialog"
import { PageHero } from "@/components/layout/PageHero"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatDate } from "@/lib/format"
import type { components } from "@/lib/schema"

type OrganizationType = components["schemas"]["OrganizationType"]

const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  fund_manager_firm: "Fund manager firm",
  investor_firm: "Investor firm",
  service_provider: "Service provider",
}

export default function SuperadminOrganizationsPage() {
  return (
    <RequireSuperadmin>
      <SuperadminOrganizationsContent />
    </RequireSuperadmin>
  )
}

function SuperadminOrganizationsContent() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  const orgsQuery = useApiQuery("/superadmin/organizations")

  const orgs = orgsQuery.data ?? []

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

      <div className="px-8 pb-16">
        <Card>
          {orgsQuery.isLoading ? (
            <CardSection>
              <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            </CardSection>
          ) : orgs.length === 0 ? (
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
