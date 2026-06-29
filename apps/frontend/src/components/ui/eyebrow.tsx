import * as React from "react"
import { cn } from "@/lib/utils"

export function Eyebrow({
  className,
  inverse,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { inverse?: boolean }) {
  return (
    <div
      className={cn(
        "es-eyebrow",
        inverse && "es-eyebrow-inverse",
        className,
      )}
      {...props}
    />
  )
}
