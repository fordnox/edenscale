import { PageHero } from "@/components/layout/PageHero"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"

export function ComingSoon({ page }: { page: string }) {
  return (
    <>
      <PageHero
        eyebrow={page}
        title={`${page} is on its way.`}
        description="This area of EdenScale is being prepared. Check back soon — the data and workflows for this section are landing in a future release."
      />
      <div className="px-8 pb-16">
        <Card>
          <CardSection className="flex flex-col gap-3">
            <Eyebrow>In progress</Eyebrow>
            <p className="font-sans text-[14px] leading-[1.6] text-ink-700 max-w-xl">
              We are building this experience deliberately. In the meantime, head back to the
              Overview to see what is happening across your funds today.
            </p>
          </CardSection>
        </Card>
      </div>
    </>
  )
}

export default ComingSoon
