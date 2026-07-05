import { Helmet } from "react-helmet-async"
import { Loader2, Users } from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Badge } from "@edenscale/ui/badge"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { formatDate } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type UserRole = components["schemas"]["UserRole"]

const ROLE_LABELS: Record<UserRole, string> = {
  superadmin: "Superadmin",
  admin: "Admin",
  fund_manager: "Fund manager",
  lp: "LP",
}

export default function UsersPage() {
  const usersQuery = useApiQuery("/superadmin/users")

  const users = usersQuery.data ?? []

  return (
    <>
      <Helmet>
        <title>{`Users · Superadmin · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Superadmin"
        title="Users."
        description="Every user on the platform across all organizations, with their memberships and roles."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <Card>
          {usersQuery.isLoading ? (
            <CardSection>
              <div className="flex min-h-[160px] items-center justify-center text-ink-500">
                <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
              </div>
            </CardSection>
          ) : users.length === 0 ? (
            <EmptyState
              icon={<Users strokeWidth={1.25} />}
              title="No users yet"
              body="Users appear here once they sign up or are provisioned as organization admins."
            />
          ) : (
            <CardSection>
              <DataTable>
                <thead>
                  <tr>
                    <TH>Name</TH>
                    <TH>Email</TH>
                    <TH>Organizations</TH>
                    <TH>Status</TH>
                    <TH>Last login</TH>
                    <TH>Created</TH>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => {
                    const fullName = [user.first_name, user.last_name]
                      .filter(Boolean)
                      .join(" ")
                      .trim()
                    return (
                      <TR key={user.id}>
                        <TD primary>
                          <span className="inline-flex items-center gap-2">
                            {fullName || "—"}
                            {user.is_superadmin && (
                              <Badge tone="info">Superadmin</Badge>
                            )}
                          </span>
                        </TD>
                        <TD>{user.email}</TD>
                        <TD>
                          {user.memberships.length === 0 ? (
                            <span className="text-ink-500">—</span>
                          ) : (
                            <span className="flex flex-wrap gap-1.5">
                              {user.memberships.map((membership) => (
                                <Badge key={membership.id} tone="neutral">
                                  {membership.organization.name} ·{" "}
                                  {ROLE_LABELS[membership.role]}
                                </Badge>
                              ))}
                            </span>
                          )}
                        </TD>
                        <TD>
                          {user.is_active ? (
                            <Badge tone="active">Active</Badge>
                          ) : (
                            <Badge tone="muted">Disabled</Badge>
                          )}
                        </TD>
                        <TD>
                          {user.last_login_at
                            ? formatDate(user.last_login_at)
                            : "Never"}
                        </TD>
                        <TD>
                          {user.created_at ? formatDate(user.created_at) : "—"}
                        </TD>
                      </TR>
                    )
                  })}
                </tbody>
              </DataTable>
            </CardSection>
          )}
        </Card>
      </div>
    </>
  )
}
