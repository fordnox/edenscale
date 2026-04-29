import * as React from "react"
import { cn } from "@/lib/utils"

export function Card({
  className,
  raised = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { raised?: boolean }) {
  return (
    <div
      className={cn(
        "border border-[var(--border-hairline)] transition-colors duration-[140ms]",
        "hover:border-[var(--border-default)]",
        raised ? "bg-raised" : "bg-surface",
        className,
      )}
      {...props}
    />
  )
}

export function CardSection({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 md:p-8", className)} {...props} />
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-end justify-between gap-4 px-6 md:px-8 pt-6 md:pt-8",
        className,
      )}
      {...props}
    />
  )
}
