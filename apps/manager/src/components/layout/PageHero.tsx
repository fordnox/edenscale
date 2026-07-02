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
  actions?: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-5 px-4 pt-6 pb-6 sm:px-6 md:flex-row md:items-end md:justify-between md:gap-6 md:px-8 md:pt-10 md:pb-8">
      <div className="flex max-w-3xl flex-col gap-3">
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h1 className="es-display text-[32px] sm:text-[40px] md:text-[52px]">
          {title}
        </h1>
        {description && (
          <p className="font-sans text-[15px] md:text-[16px] leading-[1.55] text-ink-700 max-w-xl">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-3 md:shrink-0">
          {actions}
        </div>
      )}
    </section>
  )
}
