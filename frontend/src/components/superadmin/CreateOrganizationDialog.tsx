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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useApiMutation } from "@/hooks/useApiMutation"
import type { components } from "@/lib/schema"

type OrganizationType = components["schemas"]["OrganizationType"]

const ORG_TYPE_OPTIONS: { value: OrganizationType; label: string }[] = [
  { value: "fund_manager_firm", label: "Fund manager firm" },
  { value: "investor_firm", label: "Investor firm" },
  { value: "service_provider", label: "Service provider" },
]

interface CreateOrganizationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CreateOrganizationDialog({
  open,
  onOpenChange,
}: CreateOrganizationDialogProps) {
  const queryClient = useQueryClient()

  const [name, setName] = useState("")
  const [type, setType] = useState<OrganizationType>("fund_manager_firm")
  const [legalName, setLegalName] = useState("")
  const [adminEmail, setAdminEmail] = useState("")
  const [adminFirstName, setAdminFirstName] = useState("")
  const [adminLastName, setAdminLastName] = useState("")

  const createOrg = useApiMutation("post", "/superadmin/organizations", {
    onSuccess: (response) => {
      toast.success(`Created ${response.organization.name}`)
      queryClient.invalidateQueries({
        queryKey: ["/superadmin/organizations"],
      })
      reset()
      onOpenChange(false)
    },
  })

  function reset() {
    setName("")
    setType("fund_manager_firm")
    setLegalName("")
    setAdminEmail("")
    setAdminFirstName("")
    setAdminLastName("")
  }

  function handleOpenChange(next: boolean) {
    if (!next && createOrg.isPending) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (createOrg.isPending) return
    if (!name.trim()) {
      toast.error("Name is required")
      return
    }
    if (!adminEmail.trim()) {
      toast.error("Founding admin email is required")
      return
    }
    createOrg.mutate({
      body: {
        name: name.trim(),
        type,
        legal_name: legalName.trim() ? legalName.trim() : null,
        admin_email: adminEmail.trim(),
        admin_first_name: adminFirstName.trim() ? adminFirstName.trim() : null,
        admin_last_name: adminLastName.trim() ? adminLastName.trim() : null,
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Create organization
          </DialogTitle>
          <DialogDescription>
            Provision a new firm and assign its founding administrator. The
            admin will be able to claim the account by signing in with this
            email.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="create-org-name">Name</Label>
              <Input
                id="create-org-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="create-org-type">Type</Label>
              <Select
                value={type}
                onValueChange={(value) => setType(value as OrganizationType)}
              >
                <SelectTrigger id="create-org-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ORG_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="create-org-legal-name">Legal name (optional)</Label>
            <Input
              id="create-org-legal-name"
              value={legalName}
              onChange={(event) => setLegalName(event.target.value)}
              placeholder="Eden Capital Partners, LP"
            />
          </div>
          <div className="es-rule mt-2 border-t border-[color:var(--border-hairline)] pt-4">
            <p className="font-sans text-[11px] tracking-[0.06em] uppercase text-ink-500">
              Founding administrator
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="create-org-admin-email">Email</Label>
            <Input
              id="create-org-admin-email"
              type="email"
              value={adminEmail}
              onChange={(event) => setAdminEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="create-org-admin-first-name">
                First name (optional)
              </Label>
              <Input
                id="create-org-admin-first-name"
                value={adminFirstName}
                onChange={(event) => setAdminFirstName(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="create-org-admin-last-name">
                Last name (optional)
              </Label>
              <Input
                id="create-org-admin-last-name"
                value={adminLastName}
                onChange={(event) => setAdminLastName(event.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={createOrg.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={
                createOrg.isPending || !name.trim() || !adminEmail.trim()
              }
            >
              {createOrg.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Create organization
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
