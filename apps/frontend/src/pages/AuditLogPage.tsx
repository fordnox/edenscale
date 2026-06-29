import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import {
  ChevronLeft,
  ChevronRight,
  History,
  Loader2,
  RotateCcw,
} from "lucide-react"

import { RequireRole } from "@/components/RequireRole"
import { PageHero } from "@/components/layout/PageHero"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/EmptyState"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { components } from "@/lib/schema"

type AuditLogRead = components["schemas"]["AuditLogRead"]
type UserRead = components["schemas"]["UserRead"]

const ACTION_OPTIONS = ["create", "update", "delete", "login"] as const
const PAGE_SIZE = 50

const ENTITY_TYPES = [
  "organization",
  "user",
  "fund",
  "fund_group",
  "fund_team_member",
  "investor",
  "investor_contact",
  "commitment",
  "capital_call",
  "capital_call_item",
  "distribution",
  "distribution_item",
  "document",
  "communication",
  "task",
  "notification",
] as const

interface AuditFilters {
  entity_type: string
  action: string
  user_id: string
  date_from: string
  date_to: string
}

const EMPTY_FILTERS: AuditFilters = {
  entity_type: "all",
  action: "all",
  user_id: "all",
  date_from: "",
  date_to: "",
}

export default function AuditLogPage() {
  return (
    <RequireRole allowed={["admin"]}>
      <AuditLogContent />
    </RequireRole>
  )
}

function fullName(user: UserRead) {
  const name = `${user.first_name} ${user.last_name}`.trim()
  return name || user.email
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

function AuditLogContent() {
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS)
  const [page, setPage] = useState(0)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const usersQuery = useApiQuery("/users")

  const userById = useMemo(() => {
    const map = new Map<number, UserRead>()
    for (const u of usersQuery.data ?? []) map.set(u.id, u)
    return map
  }, [usersQuery.data])

  const dateFromIso = useMemo(() => toIsoOrEmpty(filters.date_from), [
    filters.date_from,
  ])
  const dateToIso = useMemo(() => toIsoOrEmpty(filters.date_to), [
    filters.date_to,
  ])

  const auditQuery = useApiQuery("/audit-logs", {
    params: {
      query: {
        ...(filters.entity_type !== "all"
          ? { entity_type: filters.entity_type }
          : {}),
        ...(filters.action !== "all" ? { action: filters.action } : {}),
        ...(filters.user_id !== "all"
          ? { user_id: Number(filters.user_id) }
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
      filters.user_id !== EMPTY_FILTERS.user_id ||
      filters.date_from !== EMPTY_FILTERS.date_from ||
      filters.date_to !== EMPTY_FILTERS.date_to
    )
  }, [filters])

  const sortedUsers = useMemo(() => {
    return (usersQuery.data ?? []).slice().sort((a, b) => {
      return fullName(a).toLowerCase().localeCompare(fullName(b).toLowerCase())
    })
  }, [usersQuery.data])

  return (
    <>
      <Helmet>
        <title>{`Audit log · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Compliance"
        title="Audit log."
        description="Every create, update, and delete recorded across the workspace, with the responsible actor and the diff."
      />

      <div className="px-8 pb-16">
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
                  <Label htmlFor="audit-user">User</Label>
                  <Select
                    value={filters.user_id}
                    onValueChange={(value) => updateFilter("user_id", value)}
                  >
                    <SelectTrigger id="audit-user" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All users</SelectItem>
                      {sortedUsers.map((user) => (
                        <SelectItem key={user.id} value={String(user.id)}>
                          {fullName(user)}
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
                    : "There are no audit log entries yet. Activity will appear here as records are created, updated, and deleted."
                }
              />
            ) : (
              <>
                <DataTable>
                  <thead>
                    <tr>
                      <TH>When</TH>
                      <TH>Actor</TH>
                      <TH>Action</TH>
                      <TH>Entity</TH>
                      <TH>IP address</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const isExpanded = expandedId === row.id
                      const actor =
                        row.user_id !== null
                          ? userById.get(row.user_id)
                          : undefined
                      return (
                        <AuditRow
                          key={row.id}
                          row={row}
                          actorName={
                            row.user_id === null
                              ? "System"
                              : actor
                                ? fullName(actor)
                                : `User #${row.user_id}`
                          }
                          isExpanded={isExpanded}
                          onToggle={() =>
                            setExpandedId(isExpanded ? null : row.id)
                          }
                        />
                      )
                    })}
                  </tbody>
                </DataTable>

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
  row: AuditLogRead
  actorName: string
  isExpanded: boolean
  onToggle: () => void
}

function AuditRow({ row, actorName, isExpanded, onToggle }: AuditRowProps) {
  const entityLabel = row.entity_type
    ? `${titleCase(row.entity_type)}${row.entity_id !== null ? ` #${row.entity_id}` : ""}`
    : "—"
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
        <TD>{actorName}</TD>
        <TD>
          <Badge tone={actionTone(row.action)}>{titleCase(row.action)}</Badge>
        </TD>
        <TD>{entityLabel}</TD>
        <TD>{row.ip_address ?? "—"}</TD>
      </TR>
      {isExpanded && (
        <tr className="border-b border-[color:var(--border-hairline)] bg-parchment-100">
          <td colSpan={5} className="px-4 pb-6 pt-2 first:pl-0 last:pr-0">
            <div className="flex flex-col gap-2">
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
