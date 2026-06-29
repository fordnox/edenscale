import { useMemo, useState } from "react"
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

type UserRead = components["schemas"]["UserRead"]

type Mode = "select" | "email"

function fullName(user: UserRead) {
  const name = `${user.first_name} ${user.last_name}`.trim()
  return name || user.email
}

interface AssignAdminDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  organizationId: number
  existingUsers: UserRead[]
}

export function AssignAdminDialog({
  open,
  onOpenChange,
  organizationId,
  existingUsers,
}: AssignAdminDialogProps) {
  const queryClient = useQueryClient()

  const [mode, setMode] = useState<Mode>(
    existingUsers.length > 0 ? "select" : "email",
  )
  const [userId, setUserId] = useState<string>("")
  const [email, setEmail] = useState("")
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")

  const sortedUsers = useMemo(() => {
    return existingUsers.slice().sort((a, b) => {
      return fullName(a).toLowerCase().localeCompare(fullName(b).toLowerCase())
    })
  }, [existingUsers])

  const assignAdmin = useApiMutation(
    "post",
    "/superadmin/organizations/{organization_id}/admins",
    {
      onSuccess: () => {
        toast.success("Administrator assigned")
        queryClient.invalidateQueries({
          queryKey: [
            "/superadmin/organizations/{organization_id}/members",
          ],
        })
        queryClient.invalidateQueries({
          queryKey: ["/superadmin/organizations"],
        })
        reset()
        onOpenChange(false)
      },
    },
  )

  function reset() {
    setMode(existingUsers.length > 0 ? "select" : "email")
    setUserId("")
    setEmail("")
    setFirstName("")
    setLastName("")
  }

  function handleOpenChange(next: boolean) {
    if (!next && assignAdmin.isPending) return
    if (!next) reset()
    onOpenChange(next)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (assignAdmin.isPending) return

    if (mode === "select") {
      if (!userId) {
        toast.error("Select a user to promote")
        return
      }
      assignAdmin.mutate({
        params: { path: { organization_id: organizationId } },
        body: { user_id: Number(userId) },
      })
      return
    }

    if (!email.trim()) {
      toast.error("Email is required")
      return
    }
    assignAdmin.mutate({
      params: { path: { organization_id: organizationId } },
      body: {
        email: email.trim(),
        first_name: firstName.trim() ? firstName.trim() : null,
        last_name: lastName.trim() ? lastName.trim() : null,
      },
    })
  }

  const hasExisting = sortedUsers.length > 0

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            Assign administrator
          </DialogTitle>
          <DialogDescription>
            Promote an existing member of this organization to admin, or invite
            a new admin by email. If the chosen user already has another role
            here, it will be upgraded to admin.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {hasExisting && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="assign-admin-mode">How</Label>
              <Select
                value={mode}
                onValueChange={(value) => setMode(value as Mode)}
              >
                <SelectTrigger id="assign-admin-mode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="select">
                    Promote existing member
                  </SelectItem>
                  <SelectItem value="email">Invite by email</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {mode === "select" && hasExisting ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor="assign-admin-user">Member</Label>
              <Select value={userId} onValueChange={setUserId}>
                <SelectTrigger id="assign-admin-user" className="w-full">
                  <SelectValue placeholder="Select a member" />
                </SelectTrigger>
                <SelectContent>
                  {sortedUsers.map((user) => (
                    <SelectItem key={user.id} value={String(user.id)}>
                      {fullName(user)} · {user.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <Label htmlFor="assign-admin-email">Email</Label>
                <Input
                  id="assign-admin-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                />
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="assign-admin-first-name">
                    First name (optional)
                  </Label>
                  <Input
                    id="assign-admin-first-name"
                    value={firstName}
                    onChange={(event) => setFirstName(event.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="assign-admin-last-name">
                    Last name (optional)
                  </Label>
                  <Input
                    id="assign-admin-last-name"
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                  />
                </div>
              </div>
            </>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={assignAdmin.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={
                assignAdmin.isPending ||
                (mode === "select" && hasExisting
                  ? !userId
                  : !email.trim())
              }
            >
              {assignAdmin.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Assign admin
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
