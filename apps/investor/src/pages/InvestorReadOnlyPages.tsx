import { Helmet } from "react-helmet-async"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"

import { PageHero } from "@edenscale/ui/PageHero"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { fundPath, orgPath } from "@/lib/investorRoutes"
import { formatCurrency, formatDate, titleCase } from "@edenscale/shared/format"

function valueOf(row: unknown, key: string): unknown {
  return (row as Record<string, unknown> | null)?.[key]
}

function text(row: unknown, key: string, fallback = "—") {
  const value = valueOf(row, key)
  return value === null || value === undefined || value === "" ? fallback : String(value)
}

function currency(row: unknown, key: string) {
  const value = valueOf(row, key)
  return typeof value === "string" || typeof value === "number"
    ? formatCurrency(Number(value))
    : "—"
}

function date(row: unknown, key: string) {
  const value = valueOf(row, key)
  return typeof value === "string" ? formatDate(value) : "—"
}

function ReadOnlyPage({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <>
      <Helmet>
        <title>{`${title} · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero eyebrow="Investor portal" title={title} description={description} />
      {children}
    </>
  )
}

export function InvestorOverviewPage() {
  const { activeMembership } = useActiveOrganization()
  const overview = useApiQuery("/dashboard/overview", undefined, {
    enabled: Boolean(activeMembership?.organization_id),
  })

  return (
    <ReadOnlyPage
      title={activeMembership?.organization.name ?? "Portfolio overview"}
      description="Your accessible fund activity, documents, letters, and notifications."
    >
      <Card>
        <CardSection>
          {overview.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading overview...</p>
          ) : (
            <DataTable>
              <tbody>
                <TR>
                  <TD primary>Funds</TD>
                  <TD align="right">{text(overview.data, "funds_total", "0")}</TD>
                </TR>
                <TR>
                  <TD primary>Capital called</TD>
                  <TD align="right">{currency(overview.data, "capital_called")}</TD>
                </TR>
                <TR>
                  <TD primary>Distributions</TD>
                  <TD align="right">{currency(overview.data, "distributions_total")}</TD>
                </TR>
                <TR>
                  <TD primary>Documents</TD>
                  <TD align="right">{text(overview.data, "documents_total", "0")}</TD>
                </TR>
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorFundsPage() {
  const { activeMembership } = useActiveOrganization()
  const fundsQuery = useApiQuery("/funds")
  const funds = fundsQuery.data ?? []

  return (
    <ReadOnlyPage title="Funds" description="Funds available to your investor profile.">
      <Card>
        <CardSection>
          {funds.length === 0 ? (
            <EmptyState title="No funds" body="No funds are currently available." />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Fund</TH>
                  <TH align="right">Vintage</TH>
                  <TH align="right">Target</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {funds.map((fund: any) => (
                  <TR key={fund.id}>
                    <TD primary>
                      {activeMembership ? (
                        <Link to={fundPath(activeMembership.organization.slug, fund.slug)}>
                          {fund.name}
                        </Link>
                      ) : (
                        fund.name
                      )}
                    </TD>
                    <TD align="right">{fund.vintage_year ?? "—"}</TD>
                    <TD align="right">{formatCurrency(fund.target_size)}</TD>
                    <TD align="right">{titleCase(fund.status ?? "")}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorFundDetailPage({ fundId }: { fundId: string }) {
  const fundQuery = useApiQuery("/funds/{fund_id}", {
    params: { path: { fund_id: fundId } },
  })
  const fund: any = fundQuery.data

  return (
    <ReadOnlyPage
      title={fund?.name ?? "Fund"}
      description="Fund summary and investor-facing activity."
    >
      <Card>
        <CardSection>
          <DataTable>
            <tbody>
              <TR>
                <TD primary>Status</TD>
                <TD align="right">{titleCase(fund?.status ?? "")}</TD>
              </TR>
              <TR>
                <TD primary>Vintage</TD>
                <TD align="right">{fund?.vintage_year ?? "—"}</TD>
              </TR>
              <TR>
                <TD primary>Target size</TD>
                <TD align="right">{formatCurrency(fund?.target_size)}</TD>
              </TR>
              <TR>
                <TD primary>Current size</TD>
                <TD align="right">{formatCurrency(fund?.current_size)}</TD>
              </TR>
            </tbody>
          </DataTable>
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorCapitalCallsPage() {
  const callsQuery = useApiQuery("/capital-calls")
  const calls = callsQuery.data ?? []

  return (
    <ReadOnlyPage title="Capital calls" description="Capital call notices scoped to your access.">
      <Card>
        <CardSection>
          {calls.length === 0 ? (
            <EmptyState title="No capital calls" body="No capital calls are currently available." />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Call</TH>
                  <TH align="right">Due</TH>
                  <TH align="right">Amount</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {calls.map((call: any) => (
                  <TR key={call.id}>
                    <TD primary>{call.title ?? call.notice_title ?? "Capital call"}</TD>
                    <TD align="right">{date(call, "due_date")}</TD>
                    <TD align="right">{currency(call, "total_amount")}</TD>
                    <TD align="right">{titleCase(call.status ?? "")}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorDistributionsPage() {
  const distributionsQuery = useApiQuery("/distributions")
  const distributions = distributionsQuery.data ?? []

  return (
    <ReadOnlyPage title="Distributions" description="Distribution notices scoped to your access.">
      <Card>
        <CardSection>
          {distributions.length === 0 ? (
            <EmptyState title="No distributions" body="No distributions are currently available." />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Distribution</TH>
                  <TH align="right">Date</TH>
                  <TH align="right">Amount</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {distributions.map((distribution: any) => (
                  <TR key={distribution.id}>
                    <TD primary>{distribution.title ?? "Distribution"}</TD>
                    <TD align="right">{date(distribution, "distribution_date")}</TD>
                    <TD align="right">{currency(distribution, "total_amount")}</TD>
                    <TD align="right">{titleCase(distribution.status ?? "")}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorDocumentsPage() {
  const documentsQuery = useApiQuery("/documents")
  const documents = documentsQuery.data ?? []

  return (
    <ReadOnlyPage title="Documents" description="Documents available to your investor profile.">
      <Card>
        <CardSection>
          {documents.length === 0 ? (
            <EmptyState title="No documents" body="No documents are currently available." />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Name</TH>
                  <TH align="right">Type</TH>
                  <TH align="right">Uploaded</TH>
                </tr>
              </thead>
              <tbody>
                {documents.map((document: any) => (
                  <TR key={document.id}>
                    <TD primary>{document.title ?? document.filename ?? "Document"}</TD>
                    <TD align="right">{titleCase(document.document_type ?? "")}</TD>
                    <TD align="right">{date(document, "created_at")}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorLettersPage() {
  const lettersQuery = useApiQuery("/communications")
  const letters = (lettersQuery.data ?? []) as any[]

  return (
    <ReadOnlyPage title="Letters" description="Letters available to your investor profile.">
      <Card>
        <CardSection>
          {letters.length === 0 ? (
            <EmptyState title="No letters" body="No letters are currently available." />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Subject</TH>
                  <TH align="right">Sent</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {letters.map((letter: any) => (
                  <TR key={letter.id}>
                    <TD primary>{letter.subject ?? "Letter"}</TD>
                    <TD align="right">{date(letter, "sent_at")}</TD>
                    <TD align="right">{titleCase(letter.status ?? "")}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorNotificationsPage() {
  const notificationsQuery = useApiQuery("/notifications")
  const notifications = notificationsQuery.data ?? []

  return (
    <ReadOnlyPage title="Notifications" description="Recent notifications for your account.">
      <Card>
        <CardSection>
          {notifications.length === 0 ? (
            <EmptyState title="No notifications" body="No notifications are currently available." />
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Notification</TH>
                  <TH align="right">Created</TH>
                </tr>
              </thead>
              <tbody>
                {notifications.map((notification: any) => (
                  <TR key={notification.id}>
                    <TD primary>{notification.title ?? notification.message ?? "Notification"}</TD>
                    <TD align="right">{date(notification, "created_at")}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}

export function InvestorHomePage() {
  const { memberships, isLoading } = useActiveOrganization()

  return (
    <ReadOnlyPage title="Investor dashboard" description="Choose an organization to view your investor materials.">
      <Card>
        <CardSection>
          {isLoading || memberships.length === 0 ? (
            <EmptyState title="No organizations" body="No investor organizations are currently available." />
          ) : (
            <DataTable>
              <tbody>
                {memberships.map((membership) => (
                  <TR key={membership.organization_id}>
                    <TD primary>
                      <Link to={orgPath(membership.organization.slug)}>
                        {membership.organization.name}
                      </Link>
                    </TD>
                    <TD align="right">{titleCase(membership.role)}</TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>
    </ReadOnlyPage>
  )
}
