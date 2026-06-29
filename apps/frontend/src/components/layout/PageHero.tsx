import { Eyebrow } from "@/components/ui/eyebrow"

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
    <section className="flex items-end justify-between gap-6 px-8 pt-10 pb-8">
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
    </section>
  )
}
