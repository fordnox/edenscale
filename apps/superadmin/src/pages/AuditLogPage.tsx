import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import {
  ChevronLeft,
  ChevronRight,
  History,
  Loader2,
  RotateCcw,
} from "lucide-react"

import { PageHero } from "@edenscale/ui/PageHero"
import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { EmptyState } from "@edenscale/ui/EmptyState"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { config } from "@edenscale/api/config"
import { titleCase } from "@edenscale/shared/format"
import { cn } from "@edenscale/shared/utils"
import type { components } from "@edenscale/api/schema"

type SuperadminAuditLogRead = components["schemas"]["SuperadminAuditLogRead"]

const ACTION_OPTIONS = ["login", "create", "update", "delete"] as const
const PAGE_SIZE = 50

// Mirrors _ENTITY_TYPES in the backend's app/core/audit.py — keep in sync.
const ENTITY_TYPES = [
  "organization",
  "invitation",
  "user",
  "membership",
  "fund",
  "fund_group",
  "fund_valuation",
  "investor",
  "investor_contact",
  "commitment",
  "capital_call",
  "capital_call_item",
  "distribution",
  "distribution_item",
  "document",
  "communication",
  "communication_recipient",
  "task",
  "notification",
] as const

interface AuditFilters {
  entity_type: string
  action: string
  organization_id: string
  date_from: string
  date_to: string
}

const EMPTY_FILTERS: AuditFilters = {
  entity_type: "all",
  action: "all",
  organization_id: "all",
  date_from: "",
  date_to: "",
}

const REGION_NAMES =
  typeof Intl !== "undefined" && "DisplayNames" in Intl
    ? new Intl.DisplayNames(["en"], { type: "region" })
    : null

// Cloudflare's CF-IPCountry is ISO 3166-1 alpha-2 except for two sentinels:
// XX when the edge cannot resolve the country, T1/T2 for Tor exit nodes.
function formatCountry(code: string | null) {
  if (!code) return "—"
  if (code === "XX") return "Unknown"
  if (code === "T1" || code === "T2") return "Tor"
  try {
    return REGION_NAMES?.of(code) ?? code
  } catch {
    return code
  }
}

function formatTimestamp(value: string | null) {
  if (!value) return "—"
  const d = new Date(value)
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d)
}

function actionTone(action: string) {
  switch (action) {
    case "create":
      return "active" as const
    case "update":
      return "info" as const
    case "delete":
      return "negative" as const
    case "login":
      return "warning" as const
    default:
      return "muted" as const
  }
}

function toIsoOrEmpty(localValue: string): string | null {
  if (!localValue) return null
  const d = new Date(localValue)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

export default function AuditLogPage() {
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS)
  const [page, setPage] = useState(0)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const organizationsQuery = useApiQuery("/superadmin/organizations", {
    params: { query: { limit: 100 } },
  })

  const dateFromIso = useMemo(
    () => toIsoOrEmpty(filters.date_from),
    [filters.date_from],
  )
  const dateToIso = useMemo(
    () => toIsoOrEmpty(filters.date_to),
    [filters.date_to],
  )

  const auditQuery = useApiQuery("/superadmin/audit-logs", {
    params: {
      query: {
        ...(filters.entity_type !== "all"
          ? { entity_type: filters.entity_type }
          : {}),
        ...(filters.action !== "all" ? { action: filters.action } : {}),
        ...(filters.organization_id !== "all"
          ? { organization_id: filters.organization_id }
          : {}),
        ...(dateFromIso ? { date_from: dateFromIso } : {}),
        ...(dateToIso ? { date_to: dateToIso } : {}),
        skip: page * PAGE_SIZE,
        // Fetch one extra row so we know whether a next page exists.
        limit: PAGE_SIZE + 1,
      },
    },
  })

  const allRows = useMemo(() => auditQuery.data ?? [], [auditQuery.data])
  const rows = useMemo(() => allRows.slice(0, PAGE_SIZE), [allRows])
  const hasNext = allRows.length > PAGE_SIZE

  function updateFilter<K extends keyof AuditFilters>(
    key: K,
    value: AuditFilters[K],
  ) {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setPage(0)
    setExpandedId(null)
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS)
    setPage(0)
    setExpandedId(null)
  }

  const filtersDirty = useMemo(() => {
    return (
      filters.entity_type !== EMPTY_FILTERS.entity_type ||
      filters.action !== EMPTY_FILTERS.action ||
      filters.organization_id !== EMPTY_FILTERS.organization_id ||
      filters.date_from !== EMPTY_FILTERS.date_from ||
      filters.date_to !== EMPTY_FILTERS.date_to
    )
  }, [filters])

  const sortedOrganizations = useMemo(() => {
    return (organizationsQuery.data ?? [])
      .slice()
      .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
  }, [organizationsQuery.data])

  return (
    <>
      <Helmet>
        <title>{`Audit log · Superadmin · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Superadmin"
        title="Platform audit log."
        description="Every event on the platform across all organizations, including superadmin sign-ins, which belong to no organization and appear nowhere else."
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        <div className="flex flex-col gap-6">
          <Card>
            <CardSection>
              <div className="flex items-end justify-between gap-3">
                <Eyebrow>Filters</Eyebrow>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={resetFilters}
                  disabled={!filtersDirty}
                >
                  <RotateCcw strokeWidth={1.5} className="size-4" />
                  Reset
                </Button>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="audit-action">Action</Label>
                  <Select
                    value={filters.action}
                    onValueChange={(value) => updateFilter("action", value)}
                  >
                    <SelectTrigger id="audit-action" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All actions</SelectItem>
                      {ACTION_OPTIONS.map((action) => (
                        <SelectItem key={action} value={action}>
                          {titleCase(action)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="audit-entity-type">Entity type</Label>
                  <Select
                    value={filters.entity_type}
                    onValueChange={(value) =>
                      updateFilter("entity_type", value)
                    }
                  >
                    <SelectTrigger id="audit-entity-type" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All entity types</SelectItem>
                      {ENTITY_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {titleCase(type)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="audit-organization">Organization</Label>
                  <Select
                    value={filters.organization_id}
                    onValueChange={(value) =>
                      updateFilter("organization_id", value)
                    }
                  >
                    <SelectTrigger id="audit-organization" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All organizations</SelectItem>
                      {sortedOrganizations.map((organization) => (
                        <SelectItem
                          key={organization.id}
                          value={String(organization.id)}
                        >
                          {organization.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="audit-date-from">From</Label>
                  <Input
                    id="audit-date-from"
                    type="datetime-local"
                    value={filters.date_from}
                    onChange={(event) =>
                      updateFilter("date_from", event.target.value)
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="audit-date-to">To</Label>
                  <Input
                    id="audit-date-to"
                    type="datetime-local"
                    value={filters.date_to}
                    onChange={(event) =>
                      updateFilter("date_to", event.target.value)
                    }
                  />
                </div>
              </div>
            </CardSection>
          </Card>

          <Card>
            {auditQuery.isLoading ? (
              <CardSection>
                <div className="flex min-h-[200px] items-center justify-center text-ink-500">
                  <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
                </div>
              </CardSection>
            ) : rows.length === 0 ? (
              <EmptyState
                icon={<History strokeWidth={1.25} />}
                title="No audit entries"
                body={
                  filtersDirty
                    ? "No audit log entries match the current filters. Try clearing them to see more results."
                    : "There are no audit log entries yet. Platform activity will appear here as users sign in and records change."
                }
              />
            ) : (
              <>
                <CardSection className="pt-2 pb-0">
                  <DataTable>
                    <thead>
                      <tr>
                        <TH>When</TH>
                        <TH>Actor</TH>
                        <TH>Organization</TH>
                        <TH>Action</TH>
                        <TH>Entity</TH>
                        <TH>IP address</TH>
                        <TH>Country</TH>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => {
                        const isExpanded = expandedId === row.id
                        return (
                          <AuditRow
                            key={row.id}
                            row={row}
                            isExpanded={isExpanded}
                            onToggle={() =>
                              setExpandedId(isExpanded ? null : row.id)
                            }
                          />
                        )
                      })}
                    </tbody>
                  </DataTable>
                </CardSection>

                <div className="flex items-center justify-between gap-4 border-t border-[color:var(--border-hairline)] px-6 py-4 md:px-8">
                  <p className="font-sans text-[12px] text-ink-500">
                    Showing {page * PAGE_SIZE + 1}–
                    {page * PAGE_SIZE + rows.length}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={page === 0 || auditQuery.isFetching}
                      onClick={() => {
                        setPage((p) => Math.max(0, p - 1))
                        setExpandedId(null)
                      }}
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
                      disabled={!hasNext || auditQuery.isFetching}
                      onClick={() => {
                        setPage((p) => p + 1)
                        setExpandedId(null)
                      }}
                    >
                      Next
                      <ChevronRight strokeWidth={1.5} className="size-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}

interface AuditRowProps {
  row: SuperadminAuditLogRead
  isExpanded: boolean
  onToggle: () => void
}

function AuditRow({ row, isExpanded, onToggle }: AuditRowProps) {
  const entityLabel = row.entity_type
    ? `${titleCase(row.entity_type)}${row.entity_id !== null ? ` #${row.entity_id}` : ""}`
    : "—"
  const actorLabel =
    row.user_name ??
    row.user_email ??
    (row.user_id === null ? "System" : `User #${row.user_id.slice(0, 4)}`)
  const metadataPretty = useMemo(() => {
    if (!row.audit_metadata) return null
    try {
      return JSON.stringify(row.audit_metadata, null, 2)
    } catch {
      return String(row.audit_metadata)
    }
  }, [row.audit_metadata])

  return (
    <>
      <TR
        className="cursor-pointer"
        onClick={onToggle}
        aria-expanded={isExpanded}
      >
        <TD primary>{formatTimestamp(row.created_at)}</TD>
        <TD>
          <span className="inline-flex items-center gap-2">
            {actorLabel}
            {row.is_superadmin && <Badge tone="info">Superadmin</Badge>}
          </span>
        </TD>
        <TD>
          {row.organization_name ?? (
            <span className="text-ink-500">Platform</span>
          )}
        </TD>
        <TD>
          <Badge tone={actionTone(row.action)}>{titleCase(row.action)}</Badge>
        </TD>
        <TD>{entityLabel}</TD>
        <TD>{row.ip_address ?? "—"}</TD>
        <TD>{formatCountry(row.country)}</TD>
      </TR>
      {isExpanded && (
        <tr className="border-b border-[color:var(--border-hairline)] bg-parchment-100">
          <td colSpan={7} className="px-4 pb-6 pt-2 first:pl-0 last:pr-0">
            <div
              className={cn(
                "flex flex-col gap-2",
                !metadataPretty && !row.user_agent && "items-center text-center",
              )}
            >
              {row.user_email && (
                <>
                  <Eyebrow>Actor</Eyebrow>
                  <p className="font-sans text-[13px] text-ink-700">
                    {row.user_email}
                  </p>
                </>
              )}
              {row.user_agent && (
                <>
                  <Eyebrow>Device</Eyebrow>
                  <p className="font-mono text-[12px] leading-[1.55] text-ink-700">
                    {row.user_agent}
                  </p>
                </>
              )}
              <Eyebrow>Metadata</Eyebrow>
              {metadataPretty ? (
                <pre
                  className={cn(
                    "max-h-[420px] overflow-auto rounded border border-[color:var(--border-hairline)]",
                    "bg-surface px-4 py-3",
                    "font-mono text-[12px] leading-[1.55] text-ink-900",
                  )}
                >
                  {metadataPretty}
                </pre>
              ) : (
                <p className="font-sans text-[13px] text-ink-500">
                  No metadata recorded for this entry.
                </p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
