import * as React from "react"
import { cn } from "@edenscale/shared/utils"

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
  return <div className={cn("p-4 md:p-5", className)} {...props} />
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-end justify-between gap-3 px-4 md:px-5 pt-4 md:pt-5",
        className,
      )}
      {...props}
    />
  )
}
