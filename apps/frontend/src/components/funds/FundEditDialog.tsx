import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useApiMutation } from "@/hooks/useApiMutation"
import type { components } from "@/lib/schema"

type FundStatus = components["schemas"]["FundStatus"]
type FundRead = components["schemas"]["FundRead"]

const STATUS_OPTIONS: Array<{ value: FundStatus; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "closed", label: "Closed" },
  { value: "liquidating", label: "Liquidating" },
  { value: "archived", label: "Archived" },
]

interface FundEditDialogProps {
  fund: FundRead
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FundEditDialog({ fund, open, onOpenChange }: FundEditDialogProps) {
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

  const queryClient = useQueryClient()

  // Reset form whenever the dialog reopens against a (potentially refreshed) fund record
  useEffect(() => {
    if (open) {
      setName(fund.name)
      setLegalName(fund.legal_name ?? "")
      setVintageYear(fund.vintage_year ? String(fund.vintage_year) : "")
      setStrategy(fund.strategy ?? "")
      setCurrencyCode(fund.currency_code)
      setTargetSize(fund.target_size ?? "")
      setStatus(fund.status)
      setDescription(fund.description ?? "")
    }
  }, [open, fund])

  const updateFund = useApiMutation("patch", "/funds/{fund_id}", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}"] })
      queryClient.invalidateQueries({ queryKey: ["/funds/{fund_id}/overview"] })
      onOpenChange(false)
    },
  })

  function handleOpenChange(next: boolean) {
    if (!next && updateFund.isPending) return
    onOpenChange(next)
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
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">Edit fund</DialogTitle>
          <DialogDescription>
            Update fund metadata. Commitments, calls, and distributions are managed separately.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-fund-name">Name</Label>
            <Input
              id="edit-fund-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-fund-legal-name">Legal name</Label>
            <Input
              id="edit-fund-legal-name"
              value={legalName}
              onChange={(event) => setLegalName(event.target.value)}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-fund-vintage">Vintage year</Label>
              <Input
                id="edit-fund-vintage"
                type="number"
                inputMode="numeric"
                min={1900}
                max={2100}
                value={vintageYear}
                onChange={(event) => setVintageYear(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-fund-currency">Currency</Label>
              <Input
                id="edit-fund-currency"
                value={currencyCode}
                onChange={(event) => setCurrencyCode(event.target.value.toUpperCase())}
                maxLength={3}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-fund-strategy">Strategy</Label>
              <Input
                id="edit-fund-strategy"
                value={strategy}
                onChange={(event) => setStrategy(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-fund-target">Target size</Label>
              <Input
                id="edit-fund-target"
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
            <Label htmlFor="edit-fund-status">Status</Label>
            <Select
              value={status}
              onValueChange={(value) => setStatus(value as FundStatus)}
            >
              <SelectTrigger id="edit-fund-status" className="w-full">
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
          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-fund-description">Description</Label>
            <Textarea
              id="edit-fund-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter className="pb-[env(safe-area-inset-bottom)]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => handleOpenChange(false)}
              disabled={updateFund.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={updateFund.isPending || !name.trim()}
            >
              {updateFund.isPending && <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
