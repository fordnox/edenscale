import { Search } from "lucide-react"
import { Eyebrow } from "@/components/ui/eyebrow"

export function Topbar({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: string
  actions?: React.ReactNode
}) {
  return (
    <header className="sticky top-0 z-10 border-b border-[color:var(--border-hairline)] bg-page/85 backdrop-blur supports-[backdrop-filter]:bg-page/75">
      <div className="flex items-center justify-between gap-6 px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="relative hidden md:block">
            <Search
              strokeWidth={1.5}
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-500"
            />
            <input
              type="search"
              placeholder="Search funds, investors, documents…"
              className="h-9 w-[340px] rounded-xs border border-[color:var(--border-hairline)] bg-surface pl-9 pr-3 font-sans text-[13px] text-ink-900 placeholder:text-ink-500 focus:border-conifer-600 focus:outline-none"
            />
          </div>
        </div>
      </div>
      <div className="flex items-end justify-between gap-6 px-8 py-8">
        <div className="flex max-w-3xl flex-col gap-3">
          {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
          <h1 className="es-display text-[40px] md:text-[52px]">{title}</h1>
          {description && (
            <p className="font-sans text-[16px] leading-[1.55] text-ink-700 max-w-xl">
              {description}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 items-center gap-3">{actions}</div>
        )}
      </div>
    </header>
  )
}
