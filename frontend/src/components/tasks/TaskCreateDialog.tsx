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
import { Textarea } from "@/components/ui/textarea"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"

interface TaskCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultFundId?: number
  onCreated?: (taskId: number) => void
}

export function TaskCreateDialog({
  open,
  onOpenChange,
  defaultFundId,
  onCreated,
}: TaskCreateDialogProps) {
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [dueDate, setDueDate] = useState<string>("")
  const [fundId, setFundId] = useState<string>(
    defaultFundId ? String(defaultFundId) : "none",
  )
  const [assigneeId, setAssigneeId] = useState<string>("none")

  const queryClient = useQueryClient()
  const fundsQuery = useApiQuery("/funds", undefined, { enabled: open })
  const usersQuery = useApiQuery("/users", undefined, { enabled: open })

  const createTask = useApiMutation("post", "/tasks")

  const submitting = createTask.isPending

  function reset() {
    setTitle("")
    setDescription("")
    setDueDate("")
    setFundId(defaultFundId ? String(defaultFundId) : "none")
    setAssigneeId("none")
  }

  function handleOpenChange(next: boolean) {
    if (!next && submitting) return
    if (!next) reset()
    onOpenChange(next)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const trimmedTitle = title.trim()
    if (!trimmedTitle) return
    try {
      const created = await createTask.mutateAsync({
        body: {
          title: trimmedTitle,
          description: description.trim() ? description.trim() : null,
          fund_id: fundId !== "none" ? Number(fundId) : null,
          assigned_to_user_id:
            assigneeId !== "none" ? Number(assigneeId) : null,
          due_date: dueDate ? dueDate : null,
          status: "open",
        },
      })
      queryClient.invalidateQueries({ queryKey: ["/tasks"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
      toast.success("Task created")
      onCreated?.(created.id)
      reset()
      onOpenChange(false)
    } catch {
      // useApiMutation surfaces the error toast already
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="es-display text-[24px]">
            New task
          </DialogTitle>
          <DialogDescription>
            Capture a follow-up for the team. Assignees see the task in their
            queue and receive a notification.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="task-title">Title</Label>
            <Input
              id="task-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Counter-sign side letter amendment"
              autoFocus
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="task-description">Description (optional)</Label>
            <Textarea
              id="task-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              placeholder="Notes, context, or links."
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="task-fund">Fund (optional)</Label>
              <Select value={fundId} onValueChange={setFundId}>
                <SelectTrigger id="task-fund" className="w-full">
                  <SelectValue placeholder="No fund" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No fund</SelectItem>
                  {(fundsQuery.data ?? []).map((fund) => (
                    <SelectItem key={fund.id} value={String(fund.id)}>
                      {fund.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="task-assignee">Assignee (optional)</Label>
              <Select value={assigneeId} onValueChange={setAssigneeId}>
                <SelectTrigger id="task-assignee" className="w-full">
                  <SelectValue placeholder="Unassigned" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Unassigned</SelectItem>
                  {(usersQuery.data ?? []).map((user) => {
                    const name =
                      `${user.first_name} ${user.last_name}`.trim() ||
                      user.email
                    return (
                      <SelectItem key={user.id} value={String(user.id)}>
                        {name}
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="task-due">Due date (optional)</Label>
            <Input
              id="task-due"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
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
              disabled={submitting || !title.trim()}
            >
              {submitting && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Create task
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
