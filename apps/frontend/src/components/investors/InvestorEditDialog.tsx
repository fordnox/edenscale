import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

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

type InvestorRead = components["schemas"]["InvestorRead"]

interface InvestorEditDialogProps {
  investor: InvestorRead
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function InvestorEditDialog({
  investor,
  open,
  onOpenChange,
}: InvestorEditDialogProps) {
  const [name, setName] = useState(investor.name)
  const [investorCode, setInvestorCode] = useState(investor.investor_code ?? "")
  const [investorType, setInvestorType] = useState(investor.investor_type ?? "")
  const [accredited, setAccredited] = useState(investor.accredited === true)
  const [notes, setNotes] = useState(investor.notes ?? "")

  const queryClient = useQueryClient()

  useEffect(() => {
    if (!open) return
    setName(investor.name)
    setInvestorCode(investor.investor_code ?? "")
    setInvestorType(investor.investor_type ?? "")
    setAccredited(investor.accredited === true)
    setNotes(investor.notes ?? "")
  }, [open, investor])

  const updateInvestor = useApiMutation("patch", "/investors/{investor_id}", {
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: [
          "/investors/{investor_id}",
          { params: { path: { investor_id: investor.id } } },
        ],
      })
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
      toast.success("Investor updated", { description: data.name })
      onOpenChange(false)
    },
  })

  function handleOpenChange(next: boolean) {
    if (!next && updateInvestor.isPending) return
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || updateInvestor.isPending) return

    updateInvestor.mutate({
      params: { path: { investor_id: investor.id } },
      body: {
        name: name.trim(),
        investor_code: investorCode.trim() || null,
        investor_type: investorType.trim() || null,
        accredited,
        notes: notes.trim() || null,
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">Edit investor</DialogTitle>
          <DialogDescription>
            Update the details on record for this limited partner.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="investor-edit-name">Name</Label>
            <Input
              id="investor-edit-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Beacon Family Office"
              autoFocus
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="investor-edit-code">Investor code</Label>
              <Input
                id="investor-edit-code"
                value={investorCode}
                onChange={(event) => setInvestorCode(event.target.value)}
                placeholder="BCN-001"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="investor-edit-type">Investor type</Label>
              <Input
                id="investor-edit-type"
                value={investorType}
                onChange={(event) => setInvestorType(event.target.value)}
                placeholder="Family office"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              id="investor-edit-accredited"
              type="checkbox"
              checked={accredited}
              onChange={(event) => setAccredited(event.target.checked)}
              className="size-4 accent-conifer-700"
            />
            <Label htmlFor="investor-edit-accredited" className="font-sans text-sm">
              Accredited investor
            </Label>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="investor-edit-notes">Notes</Label>
            <Textarea
              id="investor-edit-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
              placeholder="Source of capital, KYC packet status, mandate notes"
            />
          </div>
          <DialogFooter className="pb-[env(safe-area-inset-bottom)]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => handleOpenChange(false)}
              disabled={updateInvestor.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={updateInvestor.isPending || !name.trim()}
            >
              {updateInvestor.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
