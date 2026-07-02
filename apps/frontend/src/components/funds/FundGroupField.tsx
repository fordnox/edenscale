import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"

const NONE_VALUE = "__none__"
const NEW_VALUE = "__new__"

interface FundGroupFieldProps {
  /** Selected fund group id, or "" for no group. */
  value: string
  onValueChange: (value: string) => void
  /** Only fetch the group list while the host dialog is open. */
  enabled?: boolean
}

export function FundGroupField({
  value,
  onValueChange,
  enabled = true,
}: FundGroupFieldProps) {
  const queryClient = useQueryClient()
  const groupsQuery = useApiQuery("/fund-groups", undefined, { enabled })
  const groups = groupsQuery.data ?? []

  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState("")

  const createGroup = useApiMutation("post", "/fund-groups")

  function handleSelect(next: string) {
    if (next === NEW_VALUE) {
      setShowNew(true)
      return
    }
    onValueChange(next === NONE_VALUE ? "" : next)
  }

  async function handleCreate() {
    const trimmed = newName.trim()
    if (!trimmed || createGroup.isPending) return
    try {
      const created = await createGroup.mutateAsync({ body: { name: trimmed } })
      queryClient.invalidateQueries({ queryKey: ["/fund-groups"] })
      onValueChange(created.id)
      setNewName("")
      setShowNew(false)
    } catch {
      // useApiMutation surfaces a toast already
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="fund-group">Fund group (optional)</Label>
      {showNew ? (
        <div className="flex items-center gap-2">
          <Input
            id="fund-group"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="New group name"
            autoFocus
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault()
                handleCreate()
              }
            }}
          />
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={handleCreate}
            disabled={!newName.trim() || createGroup.isPending}
          >
            {createGroup.isPending && (
              <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
            )}
            Create
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowNew(false)
              setNewName("")
            }}
            disabled={createGroup.isPending}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Select value={value || NONE_VALUE} onValueChange={handleSelect}>
          <SelectTrigger id="fund-group" className="w-full">
            <SelectValue placeholder="No group" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE_VALUE}>No group</SelectItem>
            {groups.map((group) => (
              <SelectItem key={group.id} value={group.id}>
                {group.name}
              </SelectItem>
            ))}
            <SelectSeparator />
            <SelectItem value={NEW_VALUE}>+ New group…</SelectItem>
          </SelectContent>
        </Select>
      )}
    </div>
  )
}
