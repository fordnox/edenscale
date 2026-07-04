import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2, Pencil, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { FundTeamMemberDialog } from "@/components/funds/FundTeamMemberDialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@edenscale/ui/alert-dialog"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useFundContext } from "@/layouts/FundLayout"
import { orgPath } from "@/lib/managerRoutes"
import type { components } from "@edenscale/api/schema"

type FundTeamMemberRead = components["schemas"]["FundTeamMemberRead"]

function memberName(member: FundTeamMemberRead) {
  const name = `${member.user.first_name} ${member.user.last_name}`.trim()
  return name || member.user.email
}

export default function FundTeamPage() {
  const queryClient = useQueryClient()
  const { orgSlug } = useParams<{ orgSlug: string }>()
  const { fund, canManage } = useFundContext()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingMember, setEditingMember] = useState<FundTeamMemberRead | null>(
    null,
  )
  const [memberToRemove, setMemberToRemove] =
    useState<FundTeamMemberRead | null>(null)

  const teamQuery = useApiQuery("/funds/{fund_id}/team", {
    params: { path: { fund_id: fund.id } },
  })
  const team = teamQuery.data ?? []

  const removeMember = useApiMutation(
    "delete",
    "/funds/{fund_id}/team/{member_id}",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: [
            "/funds/{fund_id}/team",
            { params: { path: { fund_id: fund.id } } },
          ],
        })
        toast.success("Team member removed")
        setMemberToRemove(null)
      },
    },
  )

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <Eyebrow>Team ({team.length})</Eyebrow>
        {canManage && team.length > 0 && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setEditingMember(null)
              setDialogOpen(true)
            }}
          >
            Add team member
          </Button>
        )}
      </div>
      <Card>
        <CardSection className={team.length > 0 ? "pt-2 pb-0" : undefined}>
          {teamQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : team.length === 0 ? (
            <div className="flex flex-col items-start gap-3 py-2">
              <Eyebrow>No team members assigned</Eyebrow>
              <p className="font-sans text-[14px] text-ink-700">
                Assign analysts and partners to this fund to coordinate work.
              </p>
              {canManage && (
                <div className="mt-1 flex flex-wrap items-center gap-4">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setEditingMember(null)
                      setDialogOpen(true)
                    }}
                  >
                    Add team member
                  </Button>
                  <Link
                    to={orgPath(orgSlug ?? "", "settings")}
                    className="font-sans text-[13px] font-medium text-ink-900 border-b border-brass-500 pb-0.5 hover:text-conifer-700"
                  >
                    Invite someone to the organization →
                  </Link>
                </div>
              )}
            </div>
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Name</TH>
                  <TH>Email</TH>
                  <TH>Title</TH>
                  {canManage && <TH align="right">Actions</TH>}
                </tr>
              </thead>
              <tbody>
                {team.map((member) => (
                  <TR key={member.id}>
                    <TD primary>{memberName(member)}</TD>
                    <TD>{member.user.email}</TD>
                    <TD>{member.title ?? "—"}</TD>
                    {canManage && (
                      <TD align="right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingMember(member)
                              setDialogOpen(true)
                            }}
                          >
                            <Pencil strokeWidth={1.5} className="size-4" />
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setMemberToRemove(member)}
                          >
                            <Trash2 strokeWidth={1.5} className="size-4" />
                            Remove
                          </Button>
                        </div>
                      </TD>
                    )}
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>

      <FundTeamMemberDialog
        open={dialogOpen}
        onOpenChange={(next) => {
          setDialogOpen(next)
          if (!next) setEditingMember(null)
        }}
        fundId={fund.id}
        canManage={canManage}
        member={editingMember}
        existingUserIds={team.map((m) => m.user_id)}
      />

      <AlertDialog
        open={memberToRemove !== null}
        onOpenChange={(next) => {
          if (!next) setMemberToRemove(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove team member?</AlertDialogTitle>
            <AlertDialogDescription>
              {memberToRemove ? memberName(memberToRemove) : "This member"} will be
              removed from this fund's roster. This does not affect their
              organization access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={removeMember.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (memberToRemove) {
                  removeMember.mutate({
                    params: {
                      path: { fund_id: fund.id, member_id: memberToRemove.id },
                    },
                  })
                }
              }}
              disabled={removeMember.isPending}
            >
              {removeMember.isPending && (
                <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
              )}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
