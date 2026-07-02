import { useEffect, useMemo, useState } from "react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import type { components } from "@edenscale/api/schema"

type FundTeamMemberRead = components["schemas"]["FundTeamMemberRead"]
type UserRead = components["schemas"]["UserRead"]

function userLabel(user: UserRead) {
  const name = `${user.first_name} ${user.last_name}`.trim()
  return name ? `${name} · ${user.email}` : user.email
}

interface FundTeamMemberDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  fundId: string
  /** Manager gate — the org user picker is only fetched when true. */
  canManage: boolean
  /** When set, the dialog edits an existing roster entry's title. */
  member?: FundTeamMemberRead | null
  /** User ids already on the roster — excluded from the add picker. */
  existingUserIds?: readonly string[]
}

export function FundTeamMemberDialog({
  open,
  onOpenChange,
  fundId,
  canManage,
  member,
  existingUserIds,
}: FundTeamMemberDialogProps) {
  const isEditMode = Boolean(member)

  const [userId, setUserId] = useState("")
  const [title, setTitle] = useState("")

  const queryClient = useQueryClient()

  const usersQuery = useApiQuery("/users", undefined, {
    enabled: open && canManage && !isEditMode,
  })

  useEffect(() => {
    if (open) {
      setUserId(member?.user_id ?? "")
      setTitle(member?.title ?? "")
    }
  }, [open, member])

  const addMember = useApiMutation("post", "/funds/{fund_id}/team")
  const updateMember = useApiMutation(
    "patch",
    "/funds/{fund_id}/team/{member_id}",
  )
  const submitting = addMember.isPending || updateMember.isPending

  const options = useMemo(() => {
    const taken = new Set(existingUserIds ?? [])
    return (usersQuery.data ?? [])
      .filter((user) => !taken.has(user.id))
      .map((user) => ({ id: user.id, label: userLabel(user) }))
  }, [usersQuery.data, existingUserIds])

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    onOpenChange(next)
  }

  function invalidate() {
    queryClient.invalidateQueries({
      queryKey: [
        "/funds/{fund_id}/team",
        { params: { path: { fund_id: fundId } } },
      ],
    })
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return

    const trimmedTitle = title.trim() || null

    try {
      if (isEditMode && member) {
        await updateMember.mutateAsync({
          params: { path: { fund_id: fundId, member_id: member.id } },
          body: { title: trimmedTitle },
        })
        toast.success("Team member updated")
      } else {
        if (!userId) return
        await addMember.mutateAsync({
          params: { path: { fund_id: fundId } },
          body: { user_id: userId, title: trimmedTitle },
        })
        toast.success("Team member added")
      }
      invalidate()
      onOpenChange(false)
    } catch {
      // useApiMutation surfaces a toast already; nothing else to do here
    }
  }

  const usersLoading = usersQuery.isLoading

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            {isEditMode ? "Edit team member" : "Add team member"}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update this member's title on the fund."
              : "Assign an organization user to this fund and give them an optional title."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {isEditMode ? (
            <div className="flex flex-col gap-2">
              <Label>Member</Label>
              <p className="font-sans text-[14px] text-ink-900">
                {member
                  ? `${member.user.first_name} ${member.user.last_name}`.trim() ||
                    member.user.email
                  : ""}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <Label htmlFor="team-member-user">User</Label>
              <Select value={userId} onValueChange={setUserId}>
                <SelectTrigger id="team-member-user" className="w-full">
                  <SelectValue
                    placeholder={
                      usersLoading
                        ? "Loading users…"
                        : options.length === 0
                          ? "No users available"
                          : "Select a user"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {options.map((option) => (
                    <SelectItem key={option.id} value={option.id}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!usersLoading && options.length === 0 && (
                <p className="font-sans text-[12px] text-ink-500">
                  Every organization user is already on this fund's roster.
                </p>
              )}
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="team-member-title">Title (optional)</Label>
            <Input
              id="team-member-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Lead partner, Analyst, Controller"
              maxLength={100}
            />
          </div>
          <DialogFooter className="pb-[env(safe-area-inset-bottom)]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              className="min-h-11 w-full md:min-h-9 md:w-auto"
              disabled={submitting || (!isEditMode && !userId)}
            >
              {submitting && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              {isEditMode ? "Save changes" : "Add team member"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
