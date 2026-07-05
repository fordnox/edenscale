import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@edenscale/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@edenscale/ui/dialog"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import type { components } from "@edenscale/api/schema"

type InvestorRead = components["schemas"]["InvestorRead"]

interface AddInvestorFromPayerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Payer name from the bank statement, used to prefill the investor name. */
  defaultName: string
  /** Debtor IBAN, if the statement carried one — stashed in notes for later. */
  iban?: string | null
  onCreated?: (investor: InvestorRead) => void
}

/**
 * Capture a bank-statement payer as a new investor without leaving the import
 * wizard. Uses the existing `POST /investors` endpoint (org derived from the
 * active membership) and preserves the debtor IBAN in the investor notes so the
 * bank identifier isn't lost.
 */
export function AddInvestorFromPayerDialog({
  open,
  onOpenChange,
  defaultName,
  iban,
  onCreated,
}: AddInvestorFromPayerDialogProps) {
  const [name, setName] = useState(defaultName)
  const [investorCode, setInvestorCode] = useState("")
  const queryClient = useQueryClient()
  const createInvestor = useApiMutation("post", "/investors")

  // Re-seed the name whenever the dialog opens for a different payer.
  useEffect(() => {
    if (open) {
      setName(defaultName)
      setInvestorCode("")
    }
  }, [open, defaultName])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed || createInvestor.isPending) return
    try {
      const created = await createInvestor.mutateAsync({
        body: {
          name: trimmed,
          accredited: false,
          ...(investorCode.trim()
            ? { investor_code: investorCode.trim() }
            : {}),
          ...(iban ? { notes: `IBAN: ${iban}` } : {}),
        },
      })
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      toast.success("Investor added", { description: created.name })
      onCreated?.(created)
      onOpenChange(false)
    } catch {
      // Non-401 errors surface through the api client's toast middleware.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Add payer as investor
          </DialogTitle>
          <DialogDescription>
            Creates an investor record in this organization. Set up their
            commitment afterwards to reconcile this payment against a capital
            call.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-2">
            <Label htmlFor="payer-investor-name">Name</Label>
            <Input
              id="payer-investor-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="payer-investor-code">Investor code (optional)</Label>
            <Input
              id="payer-investor-code"
              value={investorCode}
              onChange={(event) => setInvestorCode(event.target.value)}
              placeholder="e.g. ACME-01"
            />
          </div>
          {iban && (
            <p className="font-sans text-xs text-ink-500">
              IBAN {iban} will be saved to the investor's notes.
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={createInvestor.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={createInvestor.isPending || !name.trim()}
            >
              {createInvestor.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Add investor
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
