import { useState } from "react"
import { Navigate, useNavigate, useParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@edenscale/ui/alert-dialog"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { Textarea } from "@edenscale/ui/textarea"
import { FundGroupField } from "@/components/funds/FundGroupField"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useFundContext } from "@/layouts/FundLayout"
import { fundPath, orgPath } from "@/lib/managerRoutes"
import type { components } from "@edenscale/api/schema"

type FundStatus = components["schemas"]["FundStatus"]

const STATUS_OPTIONS: Array<{ value: FundStatus; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "closed", label: "Closed" },
  { value: "liquidating", label: "Liquidating" },
  { value: "archived", label: "Archived" },
]

export default function FundSettingsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { fund, canManage } = useFundContext()

  const [name, setName] = useState(fund.name)
  const [legalName, setLegalName] = useState(fund.legal_name ?? "")
  const [vintageYear, setVintageYear] = useState(
    fund.vintage_year ? String(fund.vintage_year) : "",
  )
  const [strategy, setStrategy] = useState(fund.strategy ?? "")
  const [currencyCode, setCurrencyCode] = useState(fund.currency_code)
  const [targetSize, setTargetSize] = useState(fund.target_size ?? "")
  const [status, setStatus] = useState<FundStatus>(fund.status)
  const [description, setDescription] = useState(fund.description ?? "")
  const [fundGroupId, setFundGroupId] = useState(fund.fund_group_id ?? "")
  const [archiveOpen, setArchiveOpen] = useState(false)

  const updateFund = useApiMutation("patch", "/funds/{fund_id}", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}/overview"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/by-slug/{slug}"] })
      toast.success("Fund settings saved")
    },
  })

  const archiveFund = useApiMutation("post", "/funds/{fund_id}/archive", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
      toast.success("Fund archived")
      navigate(orgPath(orgSlug ?? "", "funds"))
    },
  })

  if (!canManage) {
    return <Navigate to={fundPath(orgSlug ?? "", fund.slug)} replace />
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || updateFund.isPending) return

    const trimmedYear = vintageYear.trim()
    const yearNumber = trimmedYear ? Number(trimmedYear) : null
    const trimmedTarget = targetSize.trim()
    const trimmedCurrency = currencyCode.trim().toUpperCase()

    updateFund.mutate({
      params: { path: { fund_id: fund.id } },
      body: {
        name: name.trim(),
        legal_name: legalName.trim() || null,
        vintage_year: yearNumber && Number.isFinite(yearNumber) ? yearNumber : null,
        strategy: strategy.trim() || null,
        currency_code: trimmedCurrency.length === 3 ? trimmedCurrency : fund.currency_code,
        target_size: trimmedTarget ? trimmedTarget : null,
        status,
        description: description.trim() || null,
        fund_group_id: fundGroupId || null,
      },
    })
  }

  return (
    <div className="flex flex-col gap-8">
      <Card>
        <CardSection>
          <Eyebrow>Fund details</Eyebrow>
          <p className="mt-2 font-sans text-[14px] leading-[1.6] text-ink-700">
            Update fund metadata. Commitments, calls, and distributions are
            managed separately.
          </p>
          <form onSubmit={handleSubmit} className="mt-5 flex max-w-xl flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-settings-name">Name</Label>
              <Input
                id="fund-settings-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-settings-legal-name">Legal name</Label>
              <Input
                id="fund-settings-legal-name"
                value={legalName}
                onChange={(event) => setLegalName(event.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="fund-settings-vintage">Vintage year</Label>
                <Input
                  id="fund-settings-vintage"
                  type="number"
                  inputMode="numeric"
                  min={1900}
                  max={2100}
                  value={vintageYear}
                  onChange={(event) => setVintageYear(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="fund-settings-currency">Currency</Label>
                <Input
                  id="fund-settings-currency"
                  value={currencyCode}
                  onChange={(event) => setCurrencyCode(event.target.value.toUpperCase())}
                  maxLength={3}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="fund-settings-strategy">Strategy</Label>
                <Input
                  id="fund-settings-strategy"
                  value={strategy}
                  onChange={(event) => setStrategy(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="fund-settings-target">Target size</Label>
                <Input
                  id="fund-settings-target"
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step="0.01"
                  value={targetSize}
                  onChange={(event) => setTargetSize(event.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-settings-status">Status</Label>
              <Select
                value={status}
                onValueChange={(value) => setStatus(value as FundStatus)}
              >
                <SelectTrigger id="fund-settings-status" className="w-full">
                  <SelectValue placeholder="Select a status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <FundGroupField
              value={fundGroupId}
              onValueChange={setFundGroupId}
              enabled
            />
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-settings-description">Description</Label>
              <Textarea
                id="fund-settings-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
              />
            </div>
            <div className="mt-2">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={updateFund.isPending || !name.trim()}
              >
                {updateFund.isPending && (
                  <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                )}
                Save changes
              </Button>
            </div>
          </form>
        </CardSection>
      </Card>

      {fund.status !== "archived" && (
        <Card>
          <CardSection>
            <Eyebrow>Danger zone</Eyebrow>
            <p className="mt-2 max-w-xl font-sans text-[14px] leading-[1.6] text-ink-700">
              Archiving marks the fund as archived and hides it from active
              programme views. Existing commitments, calls, and distributions
              are retained, and the fund stays accessible by direct link.
            </p>
            <div className="mt-4">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setArchiveOpen(true)}
              >
                Archive fund
              </Button>
            </div>
          </CardSection>
        </Card>
      )}

      <AlertDialog open={archiveOpen} onOpenChange={setArchiveOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive this fund?</AlertDialogTitle>
            <AlertDialogDescription>
              {fund.name} will be marked as archived and hidden from active
              programme views. Existing commitments, calls, and distributions are
              retained. You can still access it directly.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={archiveFund.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                archiveFund.mutate({ params: { path: { fund_id: fund.id } } })
              }
              disabled={archiveFund.isPending}
            >
              {archiveFund.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Archive fund
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
