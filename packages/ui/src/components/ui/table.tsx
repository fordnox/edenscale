import * as React from "react"
import { cn } from "@edenscale/shared/utils"

export function DataTable({
  className,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table
        className={cn(
          "w-full border-collapse font-sans es-numeric",
          className,
        )}
        {...props}
      />
    </div>
  )
}

export function TH({
  className,
  align = "left",
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement> & {
  align?: "left" | "right" | "center"
}) {
  return (
    <th
      className={cn(
        "border-b border-[color:var(--border-default)]",
        "px-3 py-2.5 first:pl-0 last:pr-0",
        "font-sans text-[10px] font-semibold tracking-[0.07em] uppercase",
        "text-ink-500 whitespace-nowrap",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
      {...props}
    />
  )
}

export function TR({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "border-b border-[color:var(--border-hairline)]",
        "transition-colors duration-[140ms] hover:bg-parchment-100",
        className,
      )}
      {...props}
    />
  )
}

export function TD({
  className,
  align = "left",
  primary = false,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement> & {
  align?: "left" | "right" | "center"
  primary?: boolean
}) {
  return (
    <td
      className={cn(
        "px-3 py-2.5 first:pl-0 last:pr-0 align-middle",
        primary
          ? "text-ink-900 font-semibold text-[14px] tracking-[-0.01em]"
          : "text-ink-700 text-[13px]",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
      {...props}
    />
  )
}
