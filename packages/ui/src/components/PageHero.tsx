import type { ReactNode } from "react"
import { Eyebrow } from "@edenscale/ui/eyebrow"

export function PageHero({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <section className="flex flex-col gap-3 px-4 pt-4 pb-4 sm:px-5 md:flex-row md:items-end md:justify-between md:gap-4 md:px-6 md:pt-6 md:pb-5">
      <div className="flex max-w-3xl flex-col gap-2">
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h1 className="es-display text-[24px] sm:text-[28px] md:text-[34px]">
          {title}
        </h1>
        {description && (
          <p className="font-sans text-[14px] md:text-[15px] leading-[1.5] text-ink-700 max-w-xl">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 md:shrink-0">
          {actions}
        </div>
      )}
    </section>
  )
}
