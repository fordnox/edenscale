import { useEffect, useMemo, useState } from "react"
import { Helmet } from "react-helmet-async"
import { Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Loader2, Plus, Star } from "lucide-react"
import { toast } from "sonner"

import { PageHero } from "@/components/layout/PageHero"
import { InvestorCreateDialog } from "@/components/investors/InvestorCreateDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardSection } from "@/components/ui/card"
import { Eyebrow } from "@/components/ui/eyebrow"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { StatusPill } from "@/components/ui/StatusPill"
import { DataTable, TD, TH, TR } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApiMutation } from "@/hooks/useApiMutation"
import { useApiQuery } from "@/hooks/useApiQuery"
import { config } from "@/lib/config"
import { formatCurrency, formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"

function parseDecimal(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function InvestorDetailPanel({ investorId }: { investorId: number }) {
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

  const updateContact = useApiMutation(
    "patch",
    "/investors/{investor_id}/contacts/{contact_id}",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: [
            "/investors/{investor_id}/contacts",
            { params: { path: { investor_id: investorId } } },
          ],
        })
        toast.success("Primary contact updated")
      },
    },
  )

  const createContact = useApiMutation(
    "post",
    "/investors/{investor_id}/contacts",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: [
            "/investors/{investor_id}/contacts",
            { params: { path: { investor_id: investorId } } },
          ],
        })
        toast.success("Contact added")
      },
    },
  )

  const contacts = contactsQuery.data ?? []
  const commitments = commitmentsQuery.data ?? []
  const investor = investorQuery.data

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

  function togglePrimary(contactId: number, currentlyPrimary: boolean) {
    updateContact.mutate({
      params: {
        path: { investor_id: investorId, contact_id: contactId },
      },
      body: { is_primary: !currentlyPrimary },
    })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[color:var(--border-hairline)] px-6 py-5">
        <Eyebrow>Investor</Eyebrow>
        <h2 className="es-display mt-2 text-[28px] leading-tight">
          {investor?.name ?? "Loading…"}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-2 font-sans text-[12px] text-ink-500">
          {investor?.investor_code && (
            <span className="es-numeric">{investor.investor_code}</span>
          )}
          {investor?.investor_type && <span>· {investor.investor_type}</span>}
          {investor?.accredited && (
            <Badge tone="info" className="ml-1">
              Accredited
            </Badge>
          )}
        </div>
      </div>

      <Tabs defaultValue="contacts" className="flex-1 gap-0">
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

        <TabsContent value="contacts" className="px-6 py-5">
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
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => {
                  const isPrimary = contact.is_primary === true
                  return (
                    <TR key={contact.id}>
                      <TD>
                        <button
                          type="button"
                          onClick={() => togglePrimary(contact.id, isPrimary)}
                          disabled={updateContact.isPending}
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
                    </TR>
                  )
                })}
              </tbody>
            </DataTable>
          )}

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
              <div className="flex justify-end">
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
        </TabsContent>

        <TabsContent value="commitments" className="px-6 py-5">
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
                {commitments.map((c) => (
                  <TR key={c.id}>
                    <TD primary>
                      <Link
                        to={`/funds/${c.fund.id}`}
                        className="text-ink-900 hover:text-conifer-700"
                      >
                        {c.fund.name}
                      </Link>
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
                ))}
              </tbody>
            </DataTable>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default function InvestorsPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data, isLoading, isError } = useApiQuery("/investors")
  const investors = useMemo(() => data ?? [], [data])

  // Auto-select the first investor when the list loads
  useEffect(() => {
    if (selectedId === null && investors.length > 0) {
      setSelectedId(investors[0].id)
    }
    // If the previously selected investor was removed, fall back to the first
    if (
      selectedId !== null &&
      investors.length > 0 &&
      !investors.some((inv) => inv.id === selectedId)
    ) {
      setSelectedId(investors[0].id)
    }
  }, [investors, selectedId])

  const showEmptyState = !isLoading && !isError && investors.length === 0

  return (
    <>
      <Helmet>
        <title>{`Investors · ${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <PageHero
        eyebrow="Limited partners"
        title="Investors and commitments."
        description="A small register, kept by hand. Each line is a partner, with their contacts and commitments."
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateOpen(true)}
          >
            New investor
          </Button>
        }
      />

      <div className="px-8 pb-16">
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
              <Button
                variant="primary"
                size="sm"
                onClick={() => setCreateOpen(true)}
              >
                New investor
              </Button>
            </CardSection>
          </Card>
        )}

        {!isLoading && !isError && investors.length > 0 && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <Card>
              <CardSection className="pt-2 pb-0">
                <DataTable>
                  <thead>
                    <tr>
                      <TH>Investor</TH>
                      <TH>Type</TH>
                      <TH align="right">Funds</TH>
                      <TH align="right">Committed</TH>
                    </tr>
                  </thead>
                  <tbody>
                    {investors.map((inv) => {
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
                          <TD primary>
                            <div className="flex flex-col gap-1">
                              <span>{inv.name}</span>
                              <div className="flex items-center gap-2">
                                {inv.investor_code && (
                                  <span className="font-sans text-[11px] font-normal text-ink-500">
                                    {inv.investor_code}
                                  </span>
                                )}
                                {inv.accredited && (
                                  <Badge tone="info">Accredited</Badge>
                                )}
                              </div>
                            </div>
                          </TD>
                          <TD>{inv.investor_type ?? "—"}</TD>
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

            <Card raised className="overflow-hidden">
              {selectedId !== null ? (
                <InvestorDetailPanel
                  key={selectedId}
                  investorId={selectedId}
                />
              ) : (
                <CardSection>
                  <Eyebrow>Select an investor</Eyebrow>
                  <p className="mt-3 font-sans text-[14px] text-ink-700">
                    Choose a partner from the list to view their contacts and
                    commitments.
                  </p>
                </CardSection>
              )}
            </Card>
          </div>
        )}
      </div>

      <InvestorCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => setSelectedId(id)}
      />
    </>
  )
}
