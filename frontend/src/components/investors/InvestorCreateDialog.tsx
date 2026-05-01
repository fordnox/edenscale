import { useState } from "react"
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

interface InvestorCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: (investorId: number) => void
}

export function InvestorCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: InvestorCreateDialogProps) {
  const [name, setName] = useState("")
  const [investorCode, setInvestorCode] = useState("")
  const [investorType, setInvestorType] = useState("")
  const [accredited, setAccredited] = useState(false)
  const [notes, setNotes] = useState("")

  const queryClient = useQueryClient()

  const createInvestor = useApiMutation("post", "/investors", {
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
      toast.success("Investor created", { description: data.name })
      reset()
      onCreated?.(data.id)
      onOpenChange(false)
    },
  })

  function reset() {
    setName("")
    setInvestorCode("")
    setInvestorType("")
    setAccredited(false)
    setNotes("")
  }

  function handleOpenChange(next: boolean) {
    if (!next && createInvestor.isPending) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || createInvestor.isPending) return

    createInvestor.mutate({
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
          <DialogTitle className="es-display text-[24px]">New investor</DialogTitle>
          <DialogDescription>
            Add a limited partner to the register. Contacts and commitments are managed
            from the investor record after creation.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="investor-name">Name</Label>
            <Input
              id="investor-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Beacon Family Office"
              autoFocus
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="investor-code">Investor code</Label>
              <Input
                id="investor-code"
                value={investorCode}
                onChange={(event) => setInvestorCode(event.target.value)}
                placeholder="BCN-001"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="investor-type">Investor type</Label>
              <Input
                id="investor-type"
                value={investorType}
                onChange={(event) => setInvestorType(event.target.value)}
                placeholder="Family office"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              id="investor-accredited"
              type="checkbox"
              checked={accredited}
              onChange={(event) => setAccredited(event.target.checked)}
              className="size-4 accent-conifer-700"
            />
            <Label htmlFor="investor-accredited" className="font-sans text-sm">
              Accredited investor
            </Label>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="investor-notes">Notes</Label>
            <Textarea
              id="investor-notes"
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
              disabled={createInvestor.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={createInvestor.isPending || !name.trim()}
            >
              {createInvestor.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Create investor
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
