import { useState } from "react"
import { ArrowRight, MailCheck, X as XIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import type { components } from "@/lib/schema"

import { PendingInvitationsDialog } from "./PendingInvitationsDialog"

type InvitationRead = components["schemas"]["InvitationRead"]

interface PendingInvitationsBannerProps {
  invitations: InvitationRead[]
  onDismiss: () => void
  emphasize?: boolean
}

export function PendingInvitationsBanner({
  invitations,
  onDismiss,
  emphasize = false,
}: PendingInvitationsBannerProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const count = invitations.length

  if (count === 0) return null

  return (
    <>
      <div
        role="region"
        aria-label="Pending invitations"
        className={cn(
          "border-b border-brass-100 bg-brass-50",
          emphasize && "border-b-2",
        )}
      >
        <div className="flex items-center gap-3 px-4 py-2 md:px-8">
          <span
            aria-hidden
            className="text-brass-700 [&_svg]:size-4 [&_svg]:stroke-[1.5]"
          >
            <MailCheck />
          </span>
          <p
            className={cn(
              "min-w-0 flex-1 truncate font-sans text-[13px] text-ink-900",
              emphasize && "font-medium",
            )}
          >
            You have {count} pending invitation{count === 1 ? "" : "s"}.
          </p>
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className={cn(
              "inline-flex shrink-0 items-center gap-1 rounded-xs px-2 py-1",
              "font-sans text-[13px] font-medium text-brass-700",
              "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "hover:bg-brass-100 hover:text-ink-900",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
            )}
          >
            Review
            <ArrowRight strokeWidth={1.5} className="size-4" />
          </button>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss invitations banner"
            className={cn(
              "inline-flex size-8 shrink-0 items-center justify-center rounded-xs text-ink-700",
              "transition-colors duration-[140ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
              "hover:bg-brass-100 hover:text-ink-900",
              "focus-visible:outline-2 focus-visible:outline-conifer-600 focus-visible:outline-offset-2",
            )}
          >
            <XIcon strokeWidth={1.5} className="size-4" />
          </button>
        </div>
      </div>
      <PendingInvitationsDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        invitations={invitations}
      />
    </>
  )
}
