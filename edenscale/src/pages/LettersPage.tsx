import { Topbar } from "@/components/layout/Topbar"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Button } from "@/components/ui/button"
import { letters } from "@/data/mock"
import { formatDate } from "@/lib/format"

export function LettersPage() {
  const [featured, ...rest] = letters

  return (
    <>
      <Topbar
        eyebrow="Quarterly Letters"
        title="What we are thinking, written down."
        description="Quarterly letters are sent to limited partners on the fifteenth of the publishing month. We do not publish a market commentary in between."
        actions={
          <>
            <Button variant="secondary" size="sm">Letter archive</Button>
            <Button variant="primary" size="sm">Draft letter</Button>
          </>
        }
      />

      <div className="px-8 pb-16">
        {/* Featured letter — editorial treatment */}
        <Card raised className="overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr]">
            <CardSection className="flex flex-col gap-6 p-10 lg:p-14">
              <div className="flex items-center gap-3">
                <Eyebrow>{featured.vol}</Eyebrow>
                <span className="size-1 rounded-full bg-ink-300" />
                <span className="font-sans text-[12px] text-ink-500">
                  {formatDate(featured.sent_at, {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
                </span>
              </div>
              <h2 className="es-display text-[44px] md:text-[56px] leading-[1.05]">
                {featured.subject}.
              </h2>
              <p className="max-w-xl font-sans text-[18px] leading-[1.6] text-ink-700">
                {featured.excerpt}
              </p>
              <div className="mt-4 flex items-center gap-5">
                <Button variant="primary" size="md">
                  Read the letter
                </Button>
                <Button variant="link" size="md">
                  Forward to limited partners →
                </Button>
              </div>
              <div className="mt-2 flex items-center gap-2 font-sans text-[12px] text-ink-500">
                <span>{featured.read_minutes} min read</span>
                <span className="size-1 rounded-full bg-ink-300" />
                <span>{featured.fund_name}</span>
              </div>
            </CardSection>
            <div className="relative hidden border-l border-[color:var(--border-hairline)] lg:block">
              <div
                className="absolute inset-0"
                style={{
                  background:
                    "radial-gradient(ellipse at 30% 30%, rgba(184, 145, 92, 0.45), transparent 55%), radial-gradient(ellipse at 70% 70%, rgba(31, 61, 46, 0.65), transparent 60%), linear-gradient(180deg, #3A3A36 0%, #1A1A18 100%)",
                }}
              />
              <div className="absolute inset-0 flex items-end p-10">
                <span className="font-sans text-[10px] uppercase tracking-[0.16em] text-parchment-50/60">
                  Photograph placeholder · interior, golden hour
                </span>
              </div>
            </div>
          </div>
        </Card>

        {/* Letter archive grid */}
        <div className="mt-12">
          <div className="mb-6 flex items-end justify-between gap-4">
            <Eyebrow>Archive</Eyebrow>
            <span className="font-sans text-[12px] text-ink-500">
              {letters.length} letters published
            </span>
          </div>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            {rest.map((l) => (
              <Card key={l.id} className="flex flex-col">
                <CardSection className="flex flex-1 flex-col gap-5">
                  <Eyebrow>{l.vol}</Eyebrow>
                  <h3 className="es-display text-[24px] leading-[1.2] flex-1">
                    {l.subject}.
                  </h3>
                  <p className="font-sans text-[13px] leading-[1.6] text-ink-700">
                    {l.excerpt}
                  </p>
                  <div className="mt-2 flex items-center justify-between font-sans text-[11px] text-ink-500">
                    <span>{formatDate(l.sent_at)}</span>
                    <span>{l.read_minutes} min read</span>
                  </div>
                  <Button
                    variant="link"
                    size="sm"
                    className="self-start"
                  >
                    Read →
                  </Button>
                </CardSection>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
