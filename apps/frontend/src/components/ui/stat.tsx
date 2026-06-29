import * as React from "react"
import { cn } from "@/lib/utils"
import { Eyebrow } from "./eyebrow"

interface StatProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
  value: React.ReactNode
  unit?: string
  caption?: React.ReactNode
  trend?: "up" | "down" | "flat"
  trendLabel?: string
}

export function Stat({
  label,
  value,
  unit,
  caption,
  trend,
  trendLabel,
  className,
  ...props
}: StatProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)} {...props}>
      <Eyebrow>{label}</Eyebrow>
      <div className="flex items-baseline gap-2">
        <span className="es-numeric font-display text-[44px] leading-[1] font-medium tracking-[-0.02em] text-ink-900">
          {value}
        </span>
        {unit ? (
          <span className="font-sans text-sm text-ink-500">{unit}</span>
        ) : null}
      </div>
      {(caption || trendLabel) && (
        <div className="mt-1 flex items-center gap-2 text-[13px] text-ink-500">
          {trend && (
            <span
              className={cn(
                "es-numeric inline-flex items-center gap-1 font-medium",
                trend === "up" && "text-[color:var(--status-positive)]",
                trend === "down" && "text-[color:var(--status-negative)]",
                trend === "flat" && "text-ink-500",
              )}
            >
              {trend === "up" && "▲"}
              {trend === "down" && "▼"}
              {trend === "flat" && "—"}
              {trendLabel ? <span>{trendLabel}</span> : null}
            </span>
          )}
          {caption && <span>{caption}</span>}
        </div>
      )}
    </div>
  )
}
