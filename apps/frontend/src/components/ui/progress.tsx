import { cn } from "@/lib/utils"

export function ProgressBar({
  value,
  className,
  tone = "brand",
}: {
  value: number
  className?: string
  tone?: "brand" | "brass" | "ink"
}) {
  const pct = Math.max(0, Math.min(1, value))
  return (
    <div
      className={cn(
        "relative h-1 w-full overflow-hidden bg-parchment-200",
        className,
      )}
      role="progressbar"
      aria-valuenow={Math.round(pct * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          "absolute inset-y-0 left-0 transition-[width] duration-[220ms]",
          tone === "brand" && "bg-conifer-700",
          tone === "brass" && "bg-brass-500",
          tone === "ink" && "bg-ink-700",
        )}
        style={{ width: `${pct * 100}%` }}
      />
    </div>
  )
}
