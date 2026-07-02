import { useState } from "react"
import { Helmet } from "react-helmet-async"
import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Landmark, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { fundPath, orgPath } from "@/lib/managerRoutes"
import { config } from "@edenscale/api/config"

export default function OnboardingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setActiveOrganizationId } = useActiveOrganization()

  const [step, setStep] = useState<"firm" | "fund" | "investor">("firm")
  const [firmName, setFirmName] = useState("")
  const [legalName, setLegalName] = useState("")
  const [organizationId, setOrganizationId] = useState<string | null>(null)
  const [organizationSlug, setOrganizationSlug] = useState<string | null>(null)

  const [fundName, setFundName] = useState("")
  const [vintageYear, setVintageYear] = useState("")
  const [fundSlug, setFundSlug] = useState<string | null>(null)

  const [investorName, setInvestorName] = useState("")
  const [investorType, setInvestorType] = useState("")

  const createOrganization = useApiMutation(
    "post",
    "/organizations/self-serve",
    {
      onSuccess: (data) => {
        setActiveOrganizationId(data.organization_id)
        setOrganizationId(data.organization_id)
        setOrganizationSlug(data.organization.slug)
        setStep("fund")
      },
    },
  )

  const createFund = useApiMutation("post", "/funds", {
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      toast.success(`${data.name} is ready.`)
      setFundSlug(data.slug)
      setStep("investor")
    },
  })

  const createInvestor = useApiMutation("post", "/investors", {
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
      toast.success("Investor created", { description: data.name })
      finishOnboarding()
    },
  })

  function finishOnboarding() {
    if (organizationSlug && fundSlug) {
      navigate(fundPath(organizationSlug, fundSlug))
    } else {
      navigate(organizationSlug ? orgPath(organizationSlug) : "/manager")
    }
  }

  function handleFirmSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!firmName.trim() || createOrganization.isPending) return
    createOrganization.mutate({
      body: {
        name: firmName.trim(),
        legal_name: legalName.trim() || null,
      },
    })
  }

  function handleFundSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!fundName.trim() || !organizationId || createFund.isPending) return
    const trimmedYear = vintageYear.trim()
    const yearNumber = trimmedYear ? Number(trimmedYear) : null
    createFund.mutate({
      body: {
        name: fundName.trim(),
        vintage_year: yearNumber && Number.isFinite(yearNumber) ? yearNumber : null,
        currency_code: "USD",
        status: "draft",
      },
    })
  }

  function handleInvestorSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!investorName.trim() || !organizationId || createInvestor.isPending) return
    createInvestor.mutate({
      body: {
        name: investorName.trim(),
        investor_type: investorType.trim() || null,
        accredited: false,
      },
    })
  }

  return (
    <>
      <Helmet>
        <title>{`Set up your firm · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <div className="flex min-h-svh items-center justify-center bg-page p-6">
        <div className="w-full max-w-lg">
          <Card>
            <CardSection>
              <div className="flex flex-col gap-6">
                <div className="flex flex-col items-center gap-3 text-center">
                  <span
                    aria-hidden
                    className="text-[color:var(--brass-700)] [&_svg]:size-8 [&_svg]:stroke-[1.25]"
                  >
                    <Landmark />
                  </span>
                  {step === "firm" ? (
                    <>
                      <h1 className="font-display text-[28px] leading-[1.1] font-medium tracking-[-0.015em] text-ink-900">
                        Set up your firm.
                      </h1>
                      <p className="max-w-md font-sans text-[14px] leading-[1.6] text-ink-700">
                        You're not part of an organization yet. Create your own
                        fund manager firm to get started — you'll be its
                        administrator.
                      </p>
                    </>
                  ) : step === "fund" ? (
                    <>
                      <h1 className="font-display text-[28px] leading-[1.1] font-medium tracking-[-0.015em] text-ink-900">
                        Create your first fund.
                      </h1>
                      <p className="max-w-md font-sans text-[14px] leading-[1.6] text-ink-700">
                        {firmName.trim()} is ready. Add a fund now, or skip and
                        do it later from the Funds page.
                      </p>
                    </>
                  ) : (
                    <>
                      <h1 className="font-display text-[28px] leading-[1.1] font-medium tracking-[-0.015em] text-ink-900">
                        Add your first investor.
                      </h1>
                      <p className="max-w-md font-sans text-[14px] leading-[1.6] text-ink-700">
                        Add a limited partner to the register now, or skip and
                        do it later from the Investors page.
                      </p>
                    </>
                  )}
                </div>

                {step === "firm" ? (
                  <form
                    onSubmit={handleFirmSubmit}
                    className="flex flex-col gap-4"
                  >
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="firm-name">Firm name</Label>
                      <Input
                        id="firm-name"
                        value={firmName}
                        onChange={(event) => setFirmName(event.target.value)}
                        placeholder="NewTaven Capital"
                        autoFocus
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="firm-legal-name">
                        Legal name (optional)
                      </Label>
                      <Input
                        id="firm-legal-name"
                        value={legalName}
                        onChange={(event) => setLegalName(event.target.value)}
                        placeholder="NewTaven Capital, LLC"
                      />
                    </div>
                    <Button
                      type="submit"
                      variant="primary"
                      size="md"
                      className="mt-2"
                      disabled={createOrganization.isPending || !firmName.trim()}
                    >
                      {createOrganization.isPending && (
                        <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                      )}
                      Continue
                    </Button>
                  </form>
                ) : step === "fund" ? (
                  <form
                    onSubmit={handleFundSubmit}
                    className="flex flex-col gap-4"
                  >
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="onboarding-fund-name">Fund name</Label>
                      <Input
                        id="onboarding-fund-name"
                        value={fundName}
                        onChange={(event) => setFundName(event.target.value)}
                        placeholder="NewTaven Capital I"
                        autoFocus
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="onboarding-fund-vintage">
                        Vintage year (optional)
                      </Label>
                      <Input
                        id="onboarding-fund-vintage"
                        type="number"
                        inputMode="numeric"
                        min={1900}
                        max={2100}
                        value={vintageYear}
                        onChange={(event) => setVintageYear(event.target.value)}
                        placeholder="2026"
                      />
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Button
                        type="submit"
                        variant="primary"
                        size="md"
                        disabled={createFund.isPending || !fundName.trim()}
                      >
                        {createFund.isPending && (
                          <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                        )}
                        Create fund
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="md"
                        disabled={createFund.isPending}
                        onClick={() => setStep("investor")}
                      >
                        Skip for now
                      </Button>
                    </div>
                  </form>
                ) : (
                  <form
                    onSubmit={handleInvestorSubmit}
                    className="flex flex-col gap-4"
                  >
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="onboarding-investor-name">
                        Investor name
                      </Label>
                      <Input
                        id="onboarding-investor-name"
                        value={investorName}
                        onChange={(event) => setInvestorName(event.target.value)}
                        placeholder="Beacon Family Office"
                        autoFocus
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="onboarding-investor-type">
                        Investor type (optional)
                      </Label>
                      <Input
                        id="onboarding-investor-type"
                        value={investorType}
                        onChange={(event) => setInvestorType(event.target.value)}
                        placeholder="Family office"
                      />
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Button
                        type="submit"
                        variant="primary"
                        size="md"
                        disabled={createInvestor.isPending || !investorName.trim()}
                      >
                        {createInvestor.isPending && (
                          <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                        )}
                        Add investor
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="md"
                        disabled={createInvestor.isPending}
                        onClick={finishOnboarding}
                      >
                        Skip for now
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            </CardSection>
          </Card>
        </div>
      </div>
    </>
  )
}
