import * as React from "react"
import { Badge } from "@/components/ui/badge"
import type { components } from "@/lib/schema"

type Tone =
  | "neutral"
  | "active"
  | "muted"
  | "positive"
  | "negative"
  | "warning"
  | "info"
  | "draft"

type FundStatus = components["schemas"]["FundStatus"]
type CommitmentStatus = components["schemas"]["CommitmentStatus"]
type CapitalCallStatus = components["schemas"]["CapitalCallStatus"]
type DistributionStatus = components["schemas"]["DistributionStatus"]
type TaskStatus = components["schemas"]["TaskStatus"]
type NotificationStatus = components["schemas"]["NotificationStatus"]

export type StatusKind =
  | "fund"
  | "commitment"
  | "capital_call"
  | "distribution"
  | "task"
  | "notification"

export type StatusValueByKind = {
  fund: FundStatus
  commitment: CommitmentStatus
  capital_call: CapitalCallStatus
  distribution: DistributionStatus
  task: TaskStatus
  notification: NotificationStatus
}

const fundTones: Record<FundStatus, Tone> = {
  draft: "draft",
  active: "active",
  closed: "muted",
  liquidating: "warning",
  archived: "muted",
}

const commitmentTones: Record<CommitmentStatus, Tone> = {
  pending: "warning",
  approved: "active",
  declined: "negative",
  cancelled: "muted",
}

const capitalCallTones: Record<CapitalCallStatus, Tone> = {
  draft: "draft",
  scheduled: "info",
  sent: "info",
  partially_paid: "warning",
  paid: "positive",
  overdue: "negative",
  cancelled: "muted",
}

const distributionTones: Record<DistributionStatus, Tone> = {
  draft: "draft",
  scheduled: "info",
  sent: "info",
  partially_paid: "warning",
  paid: "positive",
  cancelled: "muted",
}

const taskTones: Record<TaskStatus, Tone> = {
  open: "info",
  in_progress: "warning",
  done: "positive",
  cancelled: "muted",
}

const notificationTones: Record<NotificationStatus, Tone> = {
  unread: "info",
  read: "muted",
  archived: "muted",
}

const toneMaps: { [K in StatusKind]: Record<StatusValueByKind[K], Tone> } = {
  fund: fundTones,
  commitment: commitmentTones,
  capital_call: capitalCallTones,
  distribution: distributionTones,
  task: taskTones,
  notification: notificationTones,
}

export function statusTone<K extends StatusKind>(
  kind: K,
  value: StatusValueByKind[K] | string,
): Tone {
  const map = toneMaps[kind] as Record<string, Tone>
  return map[value] ?? "neutral"
}

function humanize(value: string): string {
  const spaced = value.split("_").join(" ")
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

type StatusPillProps<K extends StatusKind> = Omit<
  React.HTMLAttributes<HTMLSpanElement>,
  "children"
> & {
  kind: K
  value: StatusValueByKind[K] | string
  label?: React.ReactNode
}

export function StatusPill<K extends StatusKind>({
  kind,
  value,
  label,
  ...props
}: StatusPillProps<K>) {
  const tone = statusTone(kind, value)
  return (
    <Badge tone={tone} {...props}>
      {label ?? humanize(String(value))}
    </Badge>
  )
}
