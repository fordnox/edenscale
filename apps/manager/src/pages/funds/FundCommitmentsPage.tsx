import { useState } from "react"
import { Loader2, Pencil } from "lucide-react"

import { CommitmentCreateDialog } from "@/components/commitments/CommitmentCreateDialog"
import { CommitmentEditDialog } from "@/components/commitments/CommitmentEditDialog"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { useFundContext } from "@/layouts/FundLayout"
import { formatCurrency } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type CommitmentRead = components["schemas"]["CommitmentRead"]

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export default function FundCommitmentsPage() {
  const { fund, canManage } = useFundContext()
  const [createOpen, setCreateOpen] = useState(false)
  const [editingCommitment, setEditingCommitment] =
    useState<CommitmentRead | null>(null)

  const commitmentsQuery = useApiQuery("/funds/{fund_id}/commitments", {
    params: { path: { fund_id: fund.id } },
  })
  const commitments = commitmentsQuery.data ?? []

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <Eyebrow>Commitments ({commitments.length})</Eyebrow>
        {canManage && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            New commitment
          </Button>
        )}
      </div>
      <Card>
        <CardSection className="pt-2 pb-0">
          {commitmentsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : commitments.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-8">
              <Eyebrow>No commitments yet</Eyebrow>
              <p className="font-sans text-[14px] text-ink-700">
                Investor commitments to this fund will appear here once subscriptions are recorded.
              </p>
              {canManage && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => setCreateOpen(true)}
                >
                  Record a commitment
                </Button>
              )}
            </div>
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Investor</TH>
                  <TH align="right">Committed</TH>
                  <TH align="right">Called</TH>
                  <TH align="right">Distributed</TH>
                  <TH align="right">Status</TH>
                  {canManage && <TH align="right">Actions</TH>}
                </tr>
              </thead>
              <tbody>
                {commitments.map((c) => (
                  <TR key={c.id}>
                    <TD primary>{c.investor.name}</TD>
                    <TD align="right" primary>
                      {formatCurrency(parseDecimal(c.committed_amount), fund.currency_code, {
                        compact: true,
                      })}
                    </TD>
                    <TD align="right">
                      {formatCurrency(parseDecimal(c.called_amount), fund.currency_code, {
                        compact: true,
                      })}
                    </TD>
                    <TD align="right">
                      {formatCurrency(parseDecimal(c.distributed_amount), fund.currency_code, {
                        compact: true,
                      })}
                    </TD>
                    <TD align="right">
                      <StatusPill kind="commitment" value={c.status} />
                    </TD>
                    {canManage && (
                      <TD align="right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingCommitment(c)}
                        >
                          <Pencil strokeWidth={1.5} className="size-4" />
                          Edit
                        </Button>
                      </TD>
                    )}
                  </TR>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardSection>
      </Card>

      <CommitmentCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        context={{
          kind: "fund",
          fundId: fund.id,
          fundName: fund.name,
          existingInvestorIds: commitments.map((c) => c.investor_id),
        }}
      />

      {editingCommitment && (
        <CommitmentEditDialog
          open={editingCommitment !== null}
          onOpenChange={(next) => {
            if (!next) setEditingCommitment(null)
          }}
          commitment={editingCommitment}
          fundId={fund.id}
        />
      )}
    </>
  )
}
