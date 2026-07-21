import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { ChevronLeft, ChevronRight, Loader2, MoreHorizontal, Users } from "lucide-react"
import { toast } from "sonner"

import { PageHero } from "@edenscale/ui/PageHero"
import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@edenscale/ui/dropdown-menu"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
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

// The backend now paginates this route (default limit 100). Page through it
// rather than assuming a complete roster — the platform's user list can
// outgrow a single page as the business grows.
const PAGE_SIZE = 50

export default function UsersPage() {
  const [page, setPage] = useState(0)

  const usersQuery = useApiQuery("/superadmin/users", {
    params: {
      query: {
        skip: page * PAGE_SIZE,
        // Fetch one extra row so we know whether a next page exists.
        limit: PAGE_SIZE + 1,
      },
    },
  })

  const allUsers = useMemo(() => usersQuery.data ?? [], [usersQuery.data])
  const users = useMemo(() => allUsers.slice(0, PAGE_SIZE), [allUsers])
  const hasNext = allUsers.length > PAGE_SIZE

  const sendWelcomeEmail = useApiMutation(
    "post",
    "/superadmin/users/{user_id}/send-welcome-email",
    {
      onSuccess: (data) => {
        toast.success("Welcome email sent", {
          description: data.recipient_email,
        })
      },
    },
  )

  const startInvestorDrip = useApiMutation(
    "post",
    "/superadmin/users/{user_id}/start-investor-drip",
    {
      onSuccess: (data) => {
        toast.success("Investor drip started", {
          description: data.recipient_email,
        })
      },
    },
  )

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
          ) : users.length === 0 && page === 0 ? (
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
                    <TH>
                      <span className="sr-only">Actions</span>
                    </TH>
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
                        <TD align="right">
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              aria-label="User actions"
                              className="inline-flex size-7 items-center justify-center text-ink-500 hover:text-ink-900 focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2"
                            >
                              <MoreHorizontal
                                strokeWidth={1.5}
                                className="size-4"
                              />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-52">
                              <DropdownMenuItem
                                disabled={
                                  user.memberships.length === 0 ||
                                  sendWelcomeEmail.isPending
                                }
                                onSelect={() =>
                                  sendWelcomeEmail.mutate({
                                    params: {
                                      path: { user_id: user.id },
                                    },
                                  })
                                }
                              >
                                Send Welcome Email
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                disabled={
                                  !user.memberships.some(
                                    (membership) => membership.role === "lp",
                                  ) || startInvestorDrip.isPending
                                }
                                onSelect={() =>
                                  startInvestorDrip.mutate({
                                    params: {
                                      path: { user_id: user.id },
                                    },
                                  })
                                }
                              >
                                Start Investor Drip
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TD>
                      </TR>
                    )
                  })}
                </tbody>
              </DataTable>

              <div className="flex items-center justify-between gap-4 border-t border-[color:var(--border-hairline)] px-6 py-4 md:px-8">
                <p className="font-sans text-[12px] text-ink-500">
                  Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + users.length}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={page === 0 || usersQuery.isFetching}
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
                    disabled={!hasNext || usersQuery.isFetching}
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
    </>
  )
}
