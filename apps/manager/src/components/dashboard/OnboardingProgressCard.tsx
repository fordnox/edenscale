import { useNavigate } from "react-router-dom"
import { CheckCircle2, Circle } from "lucide-react"

import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { ProgressBar } from "@edenscale/ui/progress"
import { formatPercent } from "@edenscale/shared/format"

export interface OnboardingStep {
  label: string
  caption: string
  done: boolean
  actionLabel: string
  to: string
}

function StepStatusIcon({ done }: { done: boolean }) {
  const Icon = done ? CheckCircle2 : Circle
  return (
    <Icon
      aria-hidden
      strokeWidth={1.5}
      className={done ? "size-5 text-conifer-700" : "size-5 text-ink-400"}
    />
  )
}

interface OnboardingProgressCardProps {
  steps: OnboardingStep[]
  /** Steps that can't be visited yet (e.g. no manager workspace exists). */
  isStepDisabled?: (step: OnboardingStep) => boolean
}

// The guided-setup card shared by the account and organization dashboards.
// Render it only while setup is incomplete — once every step is done the
// dashboards show the funds list (FundsListCard) in this slot instead.
export function OnboardingProgressCard({
  steps,
  isStepDisabled,
}: OnboardingProgressCardProps) {
  const navigate = useNavigate()

  const completedSteps = steps.filter((step) => step.done).length
  const progress = steps.length > 0 ? completedSteps / steps.length : 0
  const nextStep = steps.find((step) => !step.done)
  if (!nextStep) return null

  return (
    <Card>
      <div className="flex flex-col gap-5 px-6 pt-7 md:px-8 md:pt-8">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="flex flex-col gap-2">
            <Eyebrow>Onboarding progress</Eyebrow>
            <h2 className="es-display text-[28px]">{nextStep.label} is next.</h2>
            <p className="max-w-2xl font-sans text-[14px] leading-[1.6] text-ink-700">
              {nextStep.caption}
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate(nextStep.to)}
            disabled={isStepDisabled?.(nextStep) ?? false}
          >
            {nextStep.actionLabel}
          </Button>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between font-sans text-[12px] text-ink-500">
            <span>
              {completedSteps} of {steps.length} complete
            </span>
            <span className="es-numeric">{formatPercent(progress, 0)}</span>
          </div>
          <ProgressBar value={progress} tone="brass" />
        </div>
      </div>

      <CardSection className="pt-6">
        <div className="grid grid-cols-1 gap-0 border border-[color:var(--border-hairline)] md:grid-cols-2">
          {steps.map((step, index) => (
            <button
              key={step.label}
              type="button"
              onClick={() => navigate(step.to)}
              disabled={isStepDisabled?.(step) ?? false}
              className="group flex min-h-[112px] items-start gap-4 border-b border-[color:var(--border-hairline)] p-5 text-left transition-colors duration-[140ms] hover:bg-parchment-100 disabled:cursor-not-allowed disabled:opacity-60 md:[&:nth-child(odd)]:border-r md:[&:nth-last-child(-n+2)]:border-b-0"
            >
              <StepStatusIcon done={step.done} />
              <span className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="font-sans text-[14px] font-semibold text-ink-900">
                  {index + 1}. {step.label}
                </span>
                <span className="font-sans text-[13px] leading-[1.5] text-ink-500">
                  {step.caption}
                </span>
                <span className="mt-1 font-sans text-[12px] font-medium text-conifer-700 group-hover:border-b group-hover:border-brass-500">
                  {step.done ? "Review" : step.actionLabel}
                </span>
              </span>
            </button>
          ))}
        </div>
      </CardSection>
    </Card>
  )
}
