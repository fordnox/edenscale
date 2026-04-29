/**
 * Formatters for EdenScale data screens.
 * Numbers are tabular by default; currency uses code-style formatting.
 */

const DEFAULT_LOCALE = "en-GB"

export function formatCurrency(
  value: number,
  currency: string = "USD",
  opts?: { maximumFractionDigits?: number; compact?: boolean },
) {
  const compact = opts?.compact ?? false
  const max = opts?.maximumFractionDigits ?? (compact ? 2 : 0)
  return new Intl.NumberFormat(DEFAULT_LOCALE, {
    style: "currency",
    currency,
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: max,
    minimumFractionDigits: 0,
  }).format(value)
}

export function formatNumber(value: number, maximumFractionDigits = 1) {
  return new Intl.NumberFormat(DEFAULT_LOCALE, {
    maximumFractionDigits,
  }).format(value)
}

export function formatPercent(value: number, fractionDigits = 1) {
  return new Intl.NumberFormat(DEFAULT_LOCALE, {
    style: "percent",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

export function formatDate(value: string | Date, opts?: Intl.DateTimeFormatOptions) {
  const d = typeof value === "string" ? new Date(value) : value
  return new Intl.DateTimeFormat(DEFAULT_LOCALE, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...opts,
  }).format(d)
}

export function formatDateLong(value: string | Date) {
  return formatDate(value, { day: "numeric", month: "long", year: "numeric" })
}

export function formatRelativeDays(value: string | Date, today: Date) {
  const d = typeof value === "string" ? new Date(value) : value
  const diff = Math.round((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  if (diff === 0) return "Today"
  if (diff === 1) return "Tomorrow"
  if (diff === -1) return "Yesterday"
  if (diff > 0) return `In ${diff} days`
  return `${Math.abs(diff)} days ago`
}

export function titleCase(s: string) {
  return s
    .split(/[_\s]+/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ")
}
