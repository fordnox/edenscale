import { useState } from "react"
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
import { Textarea } from "@/components/ui/textarea"
import { useApiMutation } from "@/hooks/useApiMutation"
import type { components } from "@/lib/schema"

type FundStatus = components["schemas"]["FundStatus"]

const STATUS_OPTIONS: Array<{ value: FundStatus; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "closed", label: "Closed" },
  { value: "liquidating", label: "Liquidating" },
  { value: "archived", label: "Archived" },
]

interface FundCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FundCreateDialog({ open, onOpenChange }: FundCreateDialogProps) {
  const [name, setName] = useState("")
  const [legalName, setLegalName] = useState("")
  const [vintageYear, setVintageYear] = useState("")
  const [strategy, setStrategy] = useState("")
  const [currencyCode, setCurrencyCode] = useState("USD")
  const [targetSize, setTargetSize] = useState("")
  const [status, setStatus] = useState<FundStatus>("draft")
  const [description, setDescription] = useState("")

  const queryClient = useQueryClient()

  const createFund = useApiMutation("post", "/funds", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/funds"] })
      reset()
      onOpenChange(false)
    },
  })

  function reset() {
    setName("")
    setLegalName("")
    setVintageYear("")
    setStrategy("")
    setCurrencyCode("USD")
    setTargetSize("")
    setStatus("draft")
    setDescription("")
  }

  function handleOpenChange(next: boolean) {
    if (!next && createFund.isPending) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || createFund.isPending) return

    const trimmedYear = vintageYear.trim()
    const yearNumber = trimmedYear ? Number(trimmedYear) : null
    const trimmedTarget = targetSize.trim()

    createFund.mutate({
      body: {
        name: name.trim(),
        legal_name: legalName.trim() || null,
        vintage_year: yearNumber && Number.isFinite(yearNumber) ? yearNumber : null,
        strategy: strategy.trim() || null,
        currency_code: currencyCode.trim() || "USD",
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
          <DialogTitle className="es-display text-[24px]">New fund</DialogTitle>
          <DialogDescription>
            Create a fund record. You can edit details and add commitments after it is saved.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="fund-name">Name</Label>
            <Input
              id="fund-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="EdenScale Capital VI"
              autoFocus
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="fund-legal-name">Legal name</Label>
            <Input
              id="fund-legal-name"
              value={legalName}
              onChange={(event) => setLegalName(event.target.value)}
              placeholder="EdenScale Capital VI, L.P."
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-vintage">Vintage year</Label>
              <Input
                id="fund-vintage"
                type="number"
                inputMode="numeric"
                min={1900}
                max={2100}
                value={vintageYear}
                onChange={(event) => setVintageYear(event.target.value)}
                placeholder="2026"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-currency">Currency</Label>
              <Input
                id="fund-currency"
                value={currencyCode}
                onChange={(event) => setCurrencyCode(event.target.value.toUpperCase())}
                maxLength={3}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-strategy">Strategy</Label>
              <Input
                id="fund-strategy"
                value={strategy}
                onChange={(event) => setStrategy(event.target.value)}
                placeholder="Mid-market growth"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="fund-target">Target size</Label>
              <Input
                id="fund-target"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                value={targetSize}
                onChange={(event) => setTargetSize(event.target.value)}
                placeholder="500000000"
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="fund-status">Status</Label>
            <select
              id="fund-status"
              value={status}
              onChange={(event) => setStatus(event.target.value as FundStatus)}
              className="h-9 rounded-md border border-input bg-transparent px-3 py-1 font-sans text-sm text-ink-900 outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="fund-description">Description</Label>
            <Textarea
              id="fund-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              placeholder="Investment thesis, key partners, mandate"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={createFund.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={createFund.isPending || !name.trim()}
            >
              {createFund.isPending && <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />}
              Create fund
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
