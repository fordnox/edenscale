import * as React from "react"

import { cn } from "@edenscale/shared/utils"

type EmptyStateProps = {
  icon?: React.ReactNode
  title: React.ReactNode
  body?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export function EmptyState({
  icon,
  title,
  body,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 px-4 py-8 text-center",
        className,
      )}
    >
      {icon && (
        <span
          aria-hidden
          className="text-[color:var(--brass-700)] [&_svg]:size-6 [&_svg]:stroke-[1.25]"
        >
          {icon}
        </span>
      )}
      <h3 className="font-display text-[20px] leading-[1.15] font-medium tracking-[-0.015em] text-ink-900">
        {title}
      </h3>
      {body && (
        <p className="max-w-md font-sans text-[13px] leading-[1.5] text-ink-700">
          {body}
        </p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
