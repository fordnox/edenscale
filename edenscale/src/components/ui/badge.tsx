import * as React from "react"
import { cn } from "@/lib/utils"

type Tone =
  | "neutral"
  | "active"
  | "muted"
  | "positive"
  | "negative"
  | "warning"
  | "info"
  | "draft"

const toneStyles: Record<Tone, string> = {
  neutral:
    "bg-parchment-200 text-ink-700 border-[color:var(--border-hairline)]",
  active:
    "bg-conifer-50 text-conifer-700 border-conifer-100",
  muted:
    "bg-parchment-100 text-ink-500 border-[color:var(--border-hairline)]",
  positive:
    "bg-conifer-50 text-[color:var(--status-positive)] border-conifer-100",
  negative:
    "bg-[#F7E7E3] text-[color:var(--status-negative)] border-[#EAD0CA]",
  warning:
    "bg-brass-50 text-brass-700 border-brass-100",
  info:
    "bg-[#E6ECF2] text-[color:var(--status-info)] border-[#D2DCE6]",
  draft:
    "bg-parchment-100 text-ink-500 border-[color:var(--border-hairline)]",
}

export function Badge({
  tone = "neutral",
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5",
        "font-sans text-[11px] font-medium tracking-[0.04em]",
        toneStyles[tone],
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "inline-block size-1.5 rounded-full",
          tone === "active" && "bg-conifer-600",
          tone === "positive" && "bg-[color:var(--status-positive)]",
          tone === "negative" && "bg-[color:var(--status-negative)]",
          tone === "warning" && "bg-brass-500",
          tone === "info" && "bg-[color:var(--status-info)]",
          (tone === "muted" || tone === "draft" || tone === "neutral") &&
            "bg-ink-300",
        )}
      />
      {children}
    </span>
  )
}

const statusToTone: Record<string, Tone> = {
  // fund
  active: "active",
  draft: "draft",
  closed: "muted",
  liquidating: "warning",
  archived: "muted",
  // commitment
  pending: "warning",
  approved: "active",
  declined: "negative",
  cancelled: "muted",
  // capital call
  scheduled: "info",
  sent: "info",
  partially_paid: "warning",
  paid: "positive",
  overdue: "negative",
  // task
  open: "info",
  in_progress: "warning",
  done: "positive",
}

export function StatusBadge({
  status,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { status: string }) {
  const tone = statusToTone[status] ?? "neutral"
  const label = status.split("_").join(" ")
  return (
    <Badge tone={tone} {...props}>
      {label.charAt(0).toUpperCase() + label.slice(1)}
    </Badge>
  )
}
