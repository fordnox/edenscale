import { useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link, useNavigate } from "react-router-dom"
import { ArrowLeft, CheckCircle2, Loader2, UserPlus } from "lucide-react"
import { toast } from "sonner"

import { AddInvestorFromPayerDialog } from "@/components/bank-import/AddInvestorFromPayerDialog"
import { BankStatementDropzone } from "@/components/bank-import/BankStatementDropzone"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { PageHero } from "@edenscale/ui/PageHero"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { getApiBaseUrl } from "@edenscale/api/client"
import { getSessionToken } from "@edenscale/auth/hanko"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatDate } from "@edenscale/shared/format"
import type { components } from "@edenscale/api/schema"

type BankImportRead = components["schemas"]["BankImportRead"]
type BankTransactionRead = components["schemas"]["BankTransactionRead"]

type WizardStep = "upload" | "review" | "summary"

// Sentinel select values that mean "no capital-call item chosen".
const IGNORE = "__ignore__"
const UNASSIGNED = "__none__"

interface RowState {
  itemId: string // a capital_call_item_id, IGNORE, or UNASSIGNED
  amount: string
}

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-conifer-100 text-conifer-800",
  medium: "bg-brass-100 text-brass-800",
  low: "bg-[color:var(--surface-sunken)] text-ink-500",
}

function toNumber(value: string | null | undefined): number {
  if (!value) return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function initialRowState(txn: BankTransactionRead): RowState {
  const top = txn.candidates?.[0]
  if (!top) return { itemId: UNASSIGNED, amount: txn.amount }
  // Default the applied amount to whichever is smaller: what arrived, or what
  // is still outstanding on the suggested item.
  const applied = Math.min(toNumber(txn.amount), toNumber(top.remaining))
  return { itemId: top.capital_call_item_id, amount: applied.toFixed(2) }
}

export default function ImportBankPaymentsPage() {
  const navigate = useNavigate()
  const { activeMembership, activeOrganizationId, isSuperadmin } =
    useActiveOrganization()
  const canManage =
    isSuperadmin ||
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  const [step, setStep] = useState<WizardStep>("upload")
  const [isUploading, setIsUploading] = useState(false)
  const [imported, setImported] = useState<BankImportRead | null>(null)
  const [rows, setRows] = useState<Record<string, RowState>>({})
  const [appliedCount, setAppliedCount] = useState(0)
  const [payerDialog, setPayerDialog] = useState<{
    name: string
    iban: string | null
  } | null>(null)

  const applyMutation = useApiMutation(
    "post",
    "/capital-call-imports/{import_id}/apply",
  )

  // Existing investor names (normalized) so we can tell which payers are new.
  const investorsQuery = useApiQuery("/investors", undefined, {
    enabled: step === "review",
  })
  const knownPayerNames = useMemo(() => {
    const set = new Set<string>()
    for (const inv of investorsQuery.data ?? []) {
      set.add(inv.name.trim().toLowerCase())
    }
    return set
  }, [investorsQuery.data])

  const transactions = useMemo(
    () => imported?.transactions ?? [],
    [imported],
  )

  if (!canManage) {
    return (
      <div className="px-4 py-16 sm:px-6 md:px-8">
        <Eyebrow>Not available</Eyebrow>
        <p className="mt-2 font-sans text-[14px] text-ink-700">
          Only admins and fund managers can import bank payments.
        </p>
      </div>
    )
  }

  async function handleFile(file: File) {
    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append("file", file)
      const headers: Record<string, string> = {}
      const token = getSessionToken()
      if (token) headers["Authorization"] = `Bearer ${token}`
      if (activeOrganizationId)
        headers["X-Organization-Id"] = activeOrganizationId

      const response = await fetch(`${getApiBaseUrl()}/capital-call-imports`, {
        method: "POST",
        headers,
        body: formData,
      })
      if (!response.ok) {
        const detail = await response
          .clone()
          .json()
          .then((d) => d?.detail as string | undefined)
          .catch(() => undefined)
        toast.error("Could not read statement", {
          description: detail ?? `Server responded with ${response.status}`,
        })
        return
      }
      const data = (await response.json()) as BankImportRead
      setImported(data)
      const initialRows: Record<string, RowState> = {}
      for (const txn of data.transactions ?? []) {
        initialRows[txn.id] = initialRowState(txn)
      }
      setRows(initialRows)
      setStep("review")
    } catch {
      toast.error("Upload failed", {
        description: "Check your connection and try again.",
      })
    } finally {
      setIsUploading(false)
    }
  }

  function setRow(txnId: string, patch: Partial<RowState>) {
    setRows((prev) => ({ ...prev, [txnId]: { ...prev[txnId], ...patch } }))
  }

  const assignedCount = useMemo(
    () =>
      Object.values(rows).filter(
        (r) => r.itemId !== IGNORE && r.itemId !== UNASSIGNED,
      ).length,
    [rows],
  )

  async function handleApply() {
    if (!imported) return
    const assignments = transactions
      .map((txn) => {
        const row = rows[txn.id]
        if (!row || row.itemId === IGNORE || row.itemId === UNASSIGNED) {
          return null
        }
        return {
          transaction_id: txn.id,
          capital_call_item_id: row.itemId,
          amount: toNumber(row.amount).toFixed(2),
        }
      })
      .filter((a): a is NonNullable<typeof a> => a !== null)

    const ignore_transaction_ids = transactions
      .filter((txn) => rows[txn.id]?.itemId === IGNORE)
      .map((txn) => txn.id)

    if (assignments.length === 0) {
      toast.error("Nothing to apply", {
        description: "Assign at least one payment to a capital call.",
      })
      return
    }

    try {
      const result = await applyMutation.mutateAsync({
        params: { path: { import_id: imported.id } },
        body: { assignments, ignore_transaction_ids },
      })
      setAppliedCount(result.applied_count)
      setStep("summary")
      toast.success("Payments recorded", {
        description: `${result.applied_count} payment${result.applied_count === 1 ? "" : "s"} applied.`,
      })
    } catch {
      // The api client surfaces the error toast; keep the wizard on review.
    }
  }

  return (
    <>
      <Helmet>
        <title>{`Import bank payments · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Capital calls"
        title="Import payments from your bank."
        description="Drop an ISO 20022 statement and match each incoming payment to the capital call it settles."
        actions={
          <Button variant="secondary" size="sm" asChild>
            <Link to="../calls">
              <ArrowLeft strokeWidth={1.5} className="size-4" />
              Back to capital calls
            </Link>
          </Button>
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {step === "upload" && (
          <Card>
            <CardSection>
              <BankStatementDropzone
                onFile={handleFile}
                disabled={isUploading}
                isUploading={isUploading}
              />
            </CardSection>
          </Card>
        )}

        {step === "review" && imported && (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Eyebrow>{imported.file_name}</Eyebrow>
              <span className="font-sans text-[12px] text-ink-500">
                {transactions.length} incoming payment
                {transactions.length === 1 ? "" : "s"} · {assignedCount} assigned
              </span>
            </div>
            <Card>
              <CardSection className="pt-2 pb-0">
                <DataTable>
                  <thead>
                    <tr>
                      <TH>Payer</TH>
                      <TH align="right">Received</TH>
                      <TH>Assign to</TH>
                      <TH align="right">Apply</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((txn) => {
                      const row = rows[txn.id]
                      const selected = txn.candidates?.find(
                        (c) => c.capital_call_item_id === row?.itemId,
                      )
                      return (
                        <TR key={txn.id}>
                          <TD primary>
                            <div className="flex flex-col gap-1">
                              <span>{txn.debtor_name ?? "Unknown payer"}</span>
                              {txn.remittance_info && (
                                <span className="font-sans text-[11px] font-normal text-ink-500">
                                  {txn.remittance_info}
                                </span>
                              )}
                              {txn.debtor_name &&
                                (knownPayerNames.has(
                                  txn.debtor_name.trim().toLowerCase(),
                                ) ? (
                                  <span className="font-sans text-[11px] font-normal text-ink-500">
                                    ✓ In investors
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    className="flex items-center gap-1 self-start font-sans text-[11px] font-medium text-conifer-800 hover:underline"
                                    onClick={() =>
                                      setPayerDialog({
                                        name: txn.debtor_name ?? "",
                                        iban: txn.debtor_iban,
                                      })
                                    }
                                  >
                                    <UserPlus
                                      strokeWidth={1.5}
                                      className="size-3"
                                    />
                                    Add as investor
                                  </button>
                                ))}
                            </div>
                          </TD>
                          <TD align="right" primary>
                            <div className="flex flex-col items-end gap-0.5">
                              <span>
                                {formatCurrency(
                                  toNumber(txn.amount),
                                  txn.currency ?? "USD",
                                )}
                              </span>
                              {txn.value_date && (
                                <span className="font-sans text-[11px] font-normal text-ink-500">
                                  {formatDate(txn.value_date)}
                                </span>
                              )}
                            </div>
                          </TD>
                          <TD>
                            <div className="flex flex-col gap-1.5">
                              <Select
                                value={row?.itemId ?? UNASSIGNED}
                                onValueChange={(value) => {
                                  const cand = txn.candidates?.find(
                                    (c) => c.capital_call_item_id === value,
                                  )
                                  setRow(txn.id, {
                                    itemId: value,
                                    amount: cand
                                      ? Math.min(
                                          toNumber(txn.amount),
                                          toNumber(cand.remaining),
                                        ).toFixed(2)
                                      : (row?.amount ?? txn.amount),
                                  })
                                }}
                              >
                                <SelectTrigger className="min-w-[240px]">
                                  <SelectValue placeholder="Choose a capital call" />
                                </SelectTrigger>
                                <SelectContent>
                                  {(txn.candidates ?? []).map((c) => (
                                    <SelectItem
                                      key={c.capital_call_item_id}
                                      value={c.capital_call_item_id}
                                    >
                                      {c.investor_name} — {c.capital_call_title} (
                                      {formatCurrency(
                                        toNumber(c.remaining),
                                        c.currency_code,
                                      )}{" "}
                                      due)
                                    </SelectItem>
                                  ))}
                                  <SelectItem value={UNASSIGNED}>
                                    Leave unassigned
                                  </SelectItem>
                                  <SelectItem value={IGNORE}>
                                    Ignore this payment
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                              <div className="flex items-center gap-2">
                                {selected && (
                                  <span
                                    className={[
                                      "rounded px-1.5 py-0.5 font-sans text-[10px] font-medium uppercase tracking-wide",
                                      CONFIDENCE_STYLES[selected.confidence] ??
                                        CONFIDENCE_STYLES.low,
                                    ].join(" ")}
                                  >
                                    {selected.confidence} match
                                  </span>
                                )}
                                {selected?.currency_mismatch && (
                                  <span className="rounded bg-brass-100 px-1.5 py-0.5 font-sans text-[10px] font-medium uppercase tracking-wide text-brass-800">
                                    currency differs
                                  </span>
                                )}
                              </div>
                            </div>
                          </TD>
                          <TD align="right">
                            <Input
                              value={row?.amount ?? ""}
                              inputMode="decimal"
                              disabled={
                                row?.itemId === IGNORE ||
                                row?.itemId === UNASSIGNED
                              }
                              onChange={(event) =>
                                setRow(txn.id, { amount: event.target.value })
                              }
                              className="w-28 text-right"
                            />
                          </TD>
                        </TR>
                      )
                    })}
                  </tbody>
                </DataTable>
              </CardSection>
            </Card>
            <div className="mt-6 flex items-center justify-end gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setStep("upload")
                  setImported(null)
                  setRows({})
                }}
                disabled={applyMutation.isPending}
              >
                Start over
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleApply}
                disabled={applyMutation.isPending || assignedCount === 0}
              >
                {applyMutation.isPending && (
                  <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                )}
                Apply {assignedCount} payment{assignedCount === 1 ? "" : "s"}
              </Button>
            </div>
          </>
        )}

        {step === "summary" && (
          <Card>
            <CardSection className="flex flex-col items-center gap-4 py-12 text-center">
              <CheckCircle2
                strokeWidth={1.5}
                className="size-10 text-conifer-700"
              />
              <div className="flex flex-col gap-1">
                <p className="es-display text-[22px] text-ink-900">
                  {appliedCount} payment{appliedCount === 1 ? "" : "s"} recorded
                </p>
                <p className="font-sans text-[14px] text-ink-500">
                  Capital call statuses have been updated where fully paid.
                </p>
              </div>
              <div className="flex gap-3">
                <Button variant="secondary" size="sm" asChild>
                  <Link to="../calls">View capital calls</Link>
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    setStep("upload")
                    setImported(null)
                    setRows({})
                    setAppliedCount(0)
                  }}
                >
                  Import another
                </Button>
              </div>
            </CardSection>
          </Card>
        )}
      </div>

      <AddInvestorFromPayerDialog
        open={payerDialog !== null}
        onOpenChange={(next) => {
          if (!next) setPayerDialog(null)
        }}
        defaultName={payerDialog?.name ?? ""}
        iban={payerDialog?.iban ?? null}
        onCreated={() => setPayerDialog(null)}
      />
    </>
  )
}
