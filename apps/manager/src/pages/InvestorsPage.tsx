import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  Loader2,
  Mail,
  Pencil,
  Plus,
  Star,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"

import { PageHero } from "@edenscale/ui/PageHero"
import { CommitmentCreateDialog } from "@/components/commitments/CommitmentCreateDialog"
import { ContactEditDialog } from "@/components/investors/ContactEditDialog"
import { InvestorCreateDialog } from "@/components/investors/InvestorCreateDialog"
import { InviteContactDialog } from "@/components/investors/InviteContactDialog"
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
import { Badge } from "@edenscale/ui/badge"
import { Button } from "@edenscale/ui/button"
import { Card, CardSection } from "@edenscale/ui/card"
import { Eyebrow } from "@edenscale/ui/eyebrow"
import { Input } from "@edenscale/ui/input"
import { Label } from "@edenscale/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@edenscale/ui/sheet"
import { StatusPill } from "@edenscale/ui/StatusPill"
import { Textarea } from "@edenscale/ui/textarea"
import { DataTable, TD, TH, TR } from "@edenscale/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@edenscale/ui/tabs"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"
import { useApiMutation } from "@edenscale/api/hooks/useApiMutation"
import { useApiQuery } from "@edenscale/api/hooks/useApiQuery"
import { fundPath } from "@/lib/managerRoutes"
import {
  nextSortState,
  primaryContactName,
  sortInvestors,
  type SortKey,
  type SortState,
} from "@/lib/investorSort"
import { config } from "@edenscale/api/config"
import { formatCurrency, formatDate } from "@edenscale/shared/format"
import { cn } from "@edenscale/shared/utils"
import type { components } from "@edenscale/api/schema"

type InvestorContactRead = components["schemas"]["InvestorContactRead"]

interface InvestorDetailsForm {
  name: string
  investorCode: string
  investorType: string
  accredited: boolean
  notes: string
}

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

/** A TH whose label toggles the sort. Typography is inherited from TH, so the
 *  button only carries layout and the affordance. */
function SortableTH({
  label,
  sortKey,
  sort,
  onSort,
  align = "left",
}: {
  label: string
  sortKey: SortKey
  sort: SortState
  onSort: (key: SortKey) => void
  align?: "left" | "right"
}) {
  const active = sort.key === sortKey
  const Icon = !active ? ChevronsUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown
  return (
    <TH
      align={align}
      aria-sort={
        active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"
      }
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          "inline-flex items-center gap-1 font-sans text-[11px] font-semibold uppercase tracking-[0.08em]",
          "transition-colors hover:text-ink-700",
          active ? "text-ink-900" : "text-ink-500",
        )}
      >
        {label}
        <Icon
          strokeWidth={1.5}
          className={cn("size-3.5", !active && "opacity-40")}
        />
      </button>
    </TH>
  )
}

function InvestorDetailPanel({ investorId }: { investorId: string }) {
  const queryClient = useQueryClient()
  const contactsQuery = useApiQuery("/investors/{investor_id}/contacts", {
    params: { path: { investor_id: investorId } },
  })
  const commitmentsQuery = useApiQuery("/investors/{investor_id}/commitments", {
    params: { path: { investor_id: investorId } },
  })
  const investorQuery = useApiQuery("/investors/{investor_id}", {
    params: { path: { investor_id: investorId } },
  })

  function invalidateInvestorScopes() {
    queryClient.invalidateQueries({
      queryKey: [
        "/investors/{investor_id}/contacts",
        { params: { path: { investor_id: investorId } } },
      ],
    })
    queryClient.invalidateQueries({
      queryKey: [
        "/investors/{investor_id}",
        { params: { path: { investor_id: investorId } } },
      ],
    })
    queryClient.invalidateQueries({ queryKey: ["/investors"] })
    queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
  }

  const updateContact = useApiMutation(
    "patch",
    "/investors/{investor_id}/contacts/{contact_id}",
    {
      onSuccess: () => {
        toast.success("Primary contact updated")
        invalidateInvestorScopes()
      },
    },
  )

  const createContact = useApiMutation(
    "post",
    "/investors/{investor_id}/contacts",
    {
      onSuccess: () => {
        toast.success("Contact added")
        setAddContactOpen(false)
        invalidateInvestorScopes()
      },
    },
  )

  const contacts = contactsQuery.data ?? []
  const commitments = commitmentsQuery.data ?? []
  const investor = investorQuery.data

  const { activeMembership } = useActiveOrganization()
  const fundsQuery = useApiQuery("/funds")
  const funds = fundsQuery.data ?? []
  // Contacts are always invited as LPs, which fund managers are permitted to
  // do (administrators can invite staff roles elsewhere).
  const canInvite =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"
  const canManageCommitments =
    activeMembership?.role === "admin" ||
    activeMembership?.role === "fund_manager"

  const [deleteOpen, setDeleteOpen] = useState(false)
  // The details form is hydrated once the investor query resolves. Holding it
  // as null until then keeps the effect from clobbering in-progress edits.
  const [details, setDetails] = useState<InvestorDetailsForm | null>(null)
  // With no contacts the form is the whole point of the section, so it shows
  // itself; once one exists it hides behind a button.
  const [addContactOpen, setAddContactOpen] = useState(false)
  const [commitmentCreateOpen, setCommitmentCreateOpen] = useState(false)
  const [inviteContact, setInviteContact] = useState<InvestorContactRead | null>(
    null,
  )
  const [editContact, setEditContact] = useState<InvestorContactRead | null>(
    null,
  )

  useEffect(() => {
    if (investor && details === null) {
      setDetails({
        name: investor.name,
        investorCode: investor.investor_code ?? "",
        investorType: investor.investor_type ?? "",
        accredited: investor.accredited === true,
        notes: investor.notes ?? "",
      })
    }
  }, [investor, details])

  const updateInvestor = useApiMutation("patch", "/investors/{investor_id}", {
    onSuccess: (data) => {
      toast.success("Investor updated", { description: data.name })
      invalidateInvestorScopes()
    },
  })

  const detailsDirty =
    investor !== undefined &&
    details !== null &&
    (details.name !== investor.name ||
      details.investorCode !== (investor.investor_code ?? "") ||
      details.investorType !== (investor.investor_type ?? "") ||
      details.accredited !== (investor.accredited === true) ||
      details.notes !== (investor.notes ?? ""))

  function handleDetailsSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!details || !details.name.trim() || updateInvestor.isPending) return
    updateInvestor.mutate({
      params: { path: { investor_id: investorId } },
      body: {
        name: details.name.trim(),
        investor_code: details.investorCode.trim() || null,
        investor_type: details.investorType.trim() || null,
        accredited: details.accredited,
        notes: details.notes.trim() || null,
      },
    })
  }

  const deleteInvestor = useApiMutation("delete", "/investors/{investor_id}", {
    onSuccess: () => {
      toast.success("Investor deleted")
      queryClient.invalidateQueries({ queryKey: ["/investors"] })
      queryClient.invalidateQueries({ queryKey: ["/dashboard"] })
    },
  })

  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [phone, setPhone] = useState("")
  const [title, setTitle] = useState("")

  function resetContactForm() {
    setFirstName("")
    setLastName("")
    setEmail("")
    setPhone("")
    setTitle("")
  }

  function handleAddContact(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!firstName.trim() || !lastName.trim() || createContact.isPending) return
    createContact.mutate(
      {
        params: { path: { investor_id: investorId } },
        body: {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim() || null,
          phone: phone.trim() || null,
          title: title.trim() || null,
          is_primary: contacts.length === 0,
        },
      },
      {
        onSuccess: () => {
          resetContactForm()
        },
      },
    )
  }

  function togglePrimary(contactId: string, currentlyPrimary: boolean) {
    updateContact.mutate({
      params: {
        path: { investor_id: investorId, contact_id: contactId },
      },
      body: { is_primary: !currentlyPrimary },
    })
  }

  return (
    <div className="flex h-full flex-col">
      {/* pr-14 keeps a long investor name clear of the sheet's close button,
          which is absolutely positioned in this corner. */}
      <div className="border-b border-[color:var(--border-hairline)] px-6 py-5 pr-14">
        <Eyebrow>Investor</Eyebrow>
        <h2 className="es-display mt-2 text-[28px] leading-tight">
          {investor?.name ?? "Loading…"}
        </h2>
      </div>

      {investor && (
        <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete {investor.name}?</AlertDialogTitle>
              <AlertDialogDescription>
                {commitments.length > 0
                  ? "This investor still holds commitments, so the register will refuse the deletion. Cancel their commitments first."
                  : "The investor and their contacts will be removed from the register. This cannot be undone."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep investor</AlertDialogCancel>
              <AlertDialogAction
                onClick={() =>
                  deleteInvestor.mutate({
                    params: { path: { investor_id: investorId } },
                  })
                }
              >
                Delete investor
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}

      {investor && (
        <CommitmentCreateDialog
          open={commitmentCreateOpen}
          onOpenChange={setCommitmentCreateOpen}
          context={{
            kind: "investor",
            investorId: investor.id,
            investorName: investor.name,
            existingFundIds: commitments.map((c) => c.fund.id),
          }}
        />
      )}

      {investor && inviteContact && (
        <InviteContactDialog
          contact={inviteContact}
          organizationId={investor.organization_id}
          open={inviteContact !== null}
          onOpenChange={(next) => {
            if (!next) setInviteContact(null)
          }}
        />
      )}

      {editContact && (
        <ContactEditDialog
          contact={editContact}
          investorId={investorId}
          canInvite={canInvite}
          open={editContact !== null}
          onOpenChange={(next) => {
            if (!next) setEditContact(null)
          }}
          onInvite={() => {
            const contact = editContact
            setEditContact(null)
            setInviteContact(contact)
          }}
        />
      )}

      {details && (
        <form
          onSubmit={handleDetailsSubmit}
          className="border-b border-[color:var(--border-hairline)] px-6 py-5"
        >
          <Eyebrow>Details</Eyebrow>
          <div className="mt-4 flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="investor-details-name">Name</Label>
              <Input
                id="investor-details-name"
                value={details.name}
                onChange={(event) =>
                  setDetails({ ...details, name: event.target.value })
                }
                disabled={!canManageCommitments}
                required
              />
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="investor-details-code">Investor code</Label>
                <Input
                  id="investor-details-code"
                  value={details.investorCode}
                  onChange={(event) =>
                    setDetails({ ...details, investorCode: event.target.value })
                  }
                  disabled={!canManageCommitments}
                  placeholder="BCN-001"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="investor-details-type">Investor type</Label>
                <Input
                  id="investor-details-type"
                  value={details.investorType}
                  onChange={(event) =>
                    setDetails({ ...details, investorType: event.target.value })
                  }
                  disabled={!canManageCommitments}
                  placeholder="Family office"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                id="investor-details-accredited"
                type="checkbox"
                checked={details.accredited}
                onChange={(event) =>
                  setDetails({ ...details, accredited: event.target.checked })
                }
                disabled={!canManageCommitments}
                className="size-4 accent-conifer-700"
              />
              <Label
                htmlFor="investor-details-accredited"
                className="font-sans text-sm"
              >
                Accredited investor
              </Label>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="investor-details-notes">Notes</Label>
              <Textarea
                id="investor-details-notes"
                value={details.notes}
                onChange={(event) =>
                  setDetails({ ...details, notes: event.target.value })
                }
                disabled={!canManageCommitments}
                rows={3}
                placeholder="Source of capital, KYC packet status, mandate notes"
              />
            </div>
            {canManageCommitments && (
              <div className="flex items-center justify-end gap-2">
                {/* Discard only appears once there is something to discard. */}
                {detailsDirty && investor && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={updateInvestor.isPending}
                    onClick={() =>
                      setDetails({
                        name: investor.name,
                        investorCode: investor.investor_code ?? "",
                        investorType: investor.investor_type ?? "",
                        accredited: investor.accredited === true,
                        notes: investor.notes ?? "",
                      })
                    }
                  >
                    Discard
                  </Button>
                )}
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={
                    updateInvestor.isPending ||
                    !detailsDirty ||
                    !details.name.trim()
                  }
                >
                  {updateInvestor.isPending && (
                    <Loader2 strokeWidth={1.5} className="size-4 animate-spin" />
                  )}
                  Save details
                </Button>
              </div>
            )}
          </div>
        </form>
      )}

      <Tabs defaultValue="contacts" className="min-h-0 flex-1 gap-0">
        <div className="px-6 pt-4">
          <TabsList className="bg-parchment-100">
            <TabsTrigger value="contacts">
              Contacts
              <span className="ml-1 text-ink-500">({contacts.length})</span>
            </TabsTrigger>
            <TabsTrigger value="commitments">
              Commitments
              <span className="ml-1 text-ink-500">({commitments.length})</span>
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent
          value="contacts"
          className="min-h-0 overflow-y-auto px-6 py-5"
        >
          {contactsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : contacts.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-2">
              <Eyebrow>No contacts yet</Eyebrow>
              <p className="font-sans text-[13px] text-ink-700">
                Add a primary contact to receive capital call notices and letters.
              </p>
            </div>
          ) : (
            <DataTable className="mb-6">
              <thead>
                <tr>
                  <TH className="w-10"> </TH>
                  <TH>Name</TH>
                  <TH>Title</TH>
                  <TH>Email</TH>
                  <TH>Phone</TH>
                  <TH>Access</TH>
                  {canManageCommitments && <TH className="w-10"> </TH>}
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => {
                  const isPrimary = contact.is_primary === true
                  const isLinked = contact.user_id !== null
                  return (
                    <TR key={contact.id}>
                      <TD>
                        <button
                          type="button"
                          onClick={() => togglePrimary(contact.id, isPrimary)}
                          disabled={
                            updateContact.isPending || !canManageCommitments
                          }
                          aria-label={
                            isPrimary
                              ? "Unset primary contact"
                              : "Set as primary contact"
                          }
                          className={cn(
                            "inline-flex size-6 items-center justify-center rounded-full transition-colors",
                            isPrimary
                              ? "text-brass-600 hover:text-brass-700"
                              : "text-ink-300 hover:text-brass-500",
                            !canManageCommitments && "cursor-default",
                          )}
                        >
                          <Star
                            strokeWidth={1.5}
                            className={cn("size-4", isPrimary && "fill-brass-500")}
                          />
                        </button>
                      </TD>
                      <TD primary>
                        {contact.first_name} {contact.last_name}
                      </TD>
                      <TD>{contact.title ?? "—"}</TD>
                      <TD>{contact.email ?? "—"}</TD>
                      <TD>{contact.phone ?? "—"}</TD>
                      <TD>
                        {isLinked ? (
                          <Badge tone="active">Linked</Badge>
                        ) : canInvite && contact.email ? (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => setInviteContact(contact)}
                          >
                            <Mail strokeWidth={1.5} className="size-4" />
                            Invite
                          </Button>
                        ) : (
                          <span className="text-ink-500">—</span>
                        )}
                      </TD>
                      {canManageCommitments && (
                        <TD>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            aria-label={`Edit ${contact.first_name} ${contact.last_name}`}
                            onClick={() => setEditContact(contact)}
                          >
                            <Pencil strokeWidth={1.5} className="size-4" />
                          </Button>
                        </TD>
                      )}
                    </TR>
                  )
                })}
              </tbody>
            </DataTable>
          )}

          {canManageCommitments &&
            (contacts.length > 0 && !addContactOpen ? (
              <div className="border-t border-[color:var(--border-hairline)] pt-5">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setAddContactOpen(true)}
                >
                  <Plus strokeWidth={1.5} className="size-4" />
                  Add contact
                </Button>
              </div>
            ) : (
              <div className="border-t border-[color:var(--border-hairline)] pt-5">
                <Eyebrow>Add contact</Eyebrow>
                <form
                  onSubmit={handleAddContact}
                  className="mt-3 flex flex-col gap-3"
                >
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="contact-first-name">First name</Label>
                      <Input
                        id="contact-first-name"
                        value={firstName}
                        onChange={(event) => setFirstName(event.target.value)}
                        required
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="contact-last-name">Last name</Label>
                      <Input
                        id="contact-last-name"
                        value={lastName}
                        onChange={(event) => setLastName(event.target.value)}
                        required
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="contact-title">Title</Label>
                      <Input
                        id="contact-title"
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="contact-email">Email</Label>
                      <Input
                        id="contact-email"
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="contact-phone">Phone</Label>
                    <Input
                      id="contact-phone"
                      value={phone}
                      onChange={(event) => setPhone(event.target.value)}
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    {/* No way back out when this is the only contact form there is. */}
                    {contacts.length > 0 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={createContact.isPending}
                        onClick={() => {
                          resetContactForm()
                          setAddContactOpen(false)
                        }}
                      >
                        Cancel
                      </Button>
                    )}
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      disabled={
                        createContact.isPending ||
                        !firstName.trim() ||
                        !lastName.trim()
                      }
                    >
                      {createContact.isPending ? (
                        <Loader2
                          strokeWidth={1.5}
                          className="size-4 animate-spin"
                        />
                      ) : (
                        <Plus strokeWidth={1.5} className="size-4" />
                      )}
                      Add contact
                    </Button>
                  </div>
                </form>
              </div>
            ))}
        </TabsContent>

        <TabsContent
          value="commitments"
          className="min-h-0 overflow-y-auto px-6 py-5"
        >
          {canManageCommitments && commitments.length > 0 && (
            <div className="mb-3 flex justify-end">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setCommitmentCreateOpen(true)}
              >
                New commitment
              </Button>
            </div>
          )}
          {commitmentsQuery.isLoading ? (
            <div className="flex min-h-[120px] items-center justify-center text-ink-500">
              <Loader2 strokeWidth={1.5} className="size-5 animate-spin" />
            </div>
          ) : commitments.length === 0 ? (
            <div className="flex flex-col items-start gap-2 py-2">
              <Eyebrow>No commitments yet</Eyebrow>
              <p className="font-sans text-[13px] text-ink-700">
                Subscriptions to funds will appear here after they are recorded.
              </p>
              {canManageCommitments && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => setCommitmentCreateOpen(true)}
                >
                  Record a commitment
                </Button>
              )}
            </div>
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <TH>Fund</TH>
                  <TH>Date</TH>
                  <TH align="right">Committed</TH>
                  <TH align="right">Called</TH>
                  <TH align="right">Status</TH>
                </tr>
              </thead>
              <tbody>
                {commitments.map((c) => {
                  const fundSlug = funds.find((f) => f.id === c.fund.id)?.slug
                  return (
                  <TR key={c.id}>
                    <TD primary>
                      {activeMembership && fundSlug ? (
                        <Link
                          to={fundPath(activeMembership.organization.slug, fundSlug)}
                          className="text-ink-900 hover:text-conifer-700"
                        >
                          {c.fund.name}
                        </Link>
                      ) : (
                        <span>{c.fund.name}</span>
                      )}
                    </TD>
                    <TD>{formatDate(c.commitment_date)}</TD>
                    <TD align="right" primary>
                      {formatCurrency(
                        parseDecimal(c.committed_amount),
                        c.fund.currency_code,
                        { compact: true },
                      )}
                    </TD>
                    <TD align="right">
                      {formatCurrency(
                        parseDecimal(c.called_amount),
                        c.fund.currency_code,
                        { compact: true },
                      )}
                    </TD>
                    <TD align="right">
                      <StatusPill kind="commitment" value={c.status} />
                    </TD>
                  </TR>
                  )
                })}
              </tbody>
            </DataTable>
          )}
        </TabsContent>
      </Tabs>

      {/* Editing is inline above; deletion is the only thing left that needs a
          drawer-level action. */}
      {investor && canManageCommitments && (
        <div className="flex items-center justify-end border-t border-[color:var(--border-hairline)] px-6 py-4">
          <Button
            variant="ghost"
            size="sm"
            disabled={deleteInvestor.isPending}
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 strokeWidth={1.5} className="size-4" />
            Delete
          </Button>
        </div>
      )}
    </div>
  )
}

export default function InvestorsPage() {
  const { activeMembership: pageMembership } = useActiveOrganization()
  const canManageInvestors =
    pageMembership?.role === "admin" ||
    pageMembership?.role === "fund_manager"

  const [createOpen, setCreateOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, isError } = useApiQuery("/investors")
  const investors = useMemo(() => data ?? [], [data])

  const [sort, setSort] = useState<SortState>({ key: "name", dir: "asc" })
  const sortedInvestors = useMemo(
    () => sortInvestors(investors, sort),
    [investors, sort],
  )

  function handleSort(key: SortKey) {
    setSort((current) => nextSortState(current, key))
  }

  // Auto-select the first investor when the list loads
  // Nothing is selected on load — the drawer only opens on a row click. If the
  // open investor is deleted underneath us, close it rather than jumping to
  // another investor's record.
  useEffect(() => {
    if (
      selectedId !== null &&
      !sortedInvestors.some((inv) => inv.id === selectedId)
    ) {
      setSelectedId(null)
    }
  }, [sortedInvestors, selectedId])

  const showEmptyState = !isLoading && !isError && investors.length === 0

  return (
    <>
      <Helmet>
        <title>{`Investors · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Limited partners"
        title="Investors and commitments."
        description="Each line is a limited partner, with their contacts and commitments."
        actions={
          canManageInvestors ? (
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" asChild>
                {/* The bank-payments importer lets you add investors from
                    unmatched payers — the same page used for capital calls. */}
                <Link to="../calls/import">Import from Payments</Link>
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setCreateOpen(true)}
              >
                New investor
              </Button>
            </div>
          ) : undefined
        }
      />

      <div className="px-4 pb-16 sm:px-6 md:px-8">
        {isLoading && (
          <div className="flex min-h-[200px] items-center justify-center text-ink-500">
            <Loader2 strokeWidth={1.5} className="size-6 animate-spin" />
          </div>
        )}

        {isError && !isLoading && (
          <Card>
            <CardSection>
              <Eyebrow>Could not load investors</Eyebrow>
              <p className="mt-3 font-sans text-[14px] text-ink-700">
                We were unable to fetch the register. Please refresh, or try again
                in a moment.
              </p>
            </CardSection>
          </Card>
        )}

        {showEmptyState && (
          <Card>
            <CardSection className="flex flex-col items-start gap-4">
              <Eyebrow>No investors yet</Eyebrow>
              <p className="max-w-xl font-sans text-[14px] leading-[1.6] text-ink-700">
                Once limited partners are added, they will appear here with their
                commitments and contacts.
              </p>
              {canManageInvestors && (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setCreateOpen(true)}
                  >
                    New investor
                  </Button>
                  <Button variant="secondary" size="sm" asChild>
                    <Link to="../calls/import">Import from Payments</Link>
                  </Button>
                </div>
              )}
            </CardSection>
          </Card>
        )}

        {!isLoading && !isError && investors.length > 0 && (
          <Card>
            <CardSection className="pt-2 pb-0">
              <DataTable>
                <thead>
                  <tr>
                    <TH className="w-8">#</TH>
                    <SortableTH
                      label="Investor"
                      sortKey="name"
                      sort={sort}
                      onSort={handleSort}
                    />
                    <SortableTH
                      label="Code"
                      sortKey="investor_code"
                      sort={sort}
                      onSort={handleSort}
                    />
                    <SortableTH
                      label="Type"
                      sortKey="investor_type"
                      sort={sort}
                      onSort={handleSort}
                    />
                    <SortableTH
                      label="Contact"
                      sortKey="primary_contact"
                      sort={sort}
                      onSort={handleSort}
                    />
                    <SortableTH
                      label="Funds"
                      sortKey="fund_count"
                      sort={sort}
                      onSort={handleSort}
                      align="right"
                    />
                    <SortableTH
                      label="Committed"
                      sortKey="total_committed"
                      sort={sort}
                      onSort={handleSort}
                      align="right"
                    />
                  </tr>
                </thead>
                <tbody>
                  {sortedInvestors.map((inv, index) => {
                    const isSelected = inv.id === selectedId
                    return (
                      <TR
                        key={inv.id}
                        className={cn(
                          "cursor-pointer",
                          isSelected && "bg-parchment-100",
                        )}
                        onClick={() => setSelectedId(inv.id)}
                      >
                        {/* Position in the current sort, not a stable id. */}
                        <TD className="text-ink-500 tabular-nums">
                          {index + 1}
                        </TD>
                        <TD primary>
                          <div className="flex items-center gap-2">
                            <span>{inv.name}</span>
                            {inv.accredited && (
                              <Badge tone="info">Accredited</Badge>
                            )}
                          </div>
                        </TD>
                        <TD className="text-ink-500">
                          {inv.investor_code ?? "—"}
                        </TD>
                        <TD>{inv.investor_type ?? "—"}</TD>
                        <TD>{primaryContactName(inv) ?? "—"}</TD>
                        <TD align="right">{inv.fund_count}</TD>
                        <TD align="right" primary>
                          {formatCurrency(
                            parseDecimal(inv.total_committed),
                            "USD",
                            { compact: true },
                          )}
                        </TD>
                      </TR>
                    )
                  })}
                </tbody>
              </DataTable>
            </CardSection>
          </Card>
        )}
      </div>

      <Sheet
        open={selectedId !== null}
        onOpenChange={(next) => {
          if (!next) setSelectedId(null)
        }}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl flex flex-col gap-0 p-0"
        >
          <SheetTitle className="sr-only">Investor detail</SheetTitle>
          <SheetDescription className="sr-only">
            Contacts and commitments for the selected investor.
          </SheetDescription>
          {selectedId !== null && (
            <InvestorDetailPanel key={selectedId} investorId={selectedId} />
          )}
        </SheetContent>
      </Sheet>

      <InvestorCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => setSelectedId(id)}
      />
    </>
  )
}
