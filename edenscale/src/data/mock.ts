/**
 * Mock data shaped from db.dbml — the fund-manager / LP platform schema.
 * Every entity here mirrors a table in the schema (organizations, funds,
 * commitments, capital_calls, distributions, documents, communications,
 * tasks, notifications). Numbers are illustrative.
 */

export type FundStatus = "draft" | "active" | "closed" | "liquidating" | "archived"
export type CommitmentStatus = "pending" | "approved" | "declined" | "cancelled"
export type CapitalCallStatus =
  | "draft"
  | "scheduled"
  | "sent"
  | "partially_paid"
  | "paid"
  | "overdue"
  | "cancelled"
export type DistributionStatus =
  | "draft"
  | "scheduled"
  | "sent"
  | "partially_paid"
  | "paid"
  | "cancelled"
export type DocumentType =
  | "legal"
  | "kyc_aml"
  | "financial"
  | "report"
  | "notice"
  | "other"
export type CommunicationType = "announcement" | "message" | "notification"
export type TaskStatus = "open" | "in_progress" | "done" | "cancelled"

export interface Organization {
  id: number
  name: string
  legal_name: string
  type: "fund_manager_firm" | "investor_firm" | "service_provider"
}

export interface Fund {
  id: number
  organization_id: number
  fund_group_id?: number
  name: string
  legal_name: string
  vintage_year: number
  strategy: string
  currency_code: string
  target_size: number
  hard_cap: number
  current_size: number
  status: FundStatus
  inception_date: string
  description: string
  // Derived fields the LP portal exposes
  committed: number
  called: number
  distributed: number
  nav: number
  irr: number
  tvpi: number
  dpi: number
  investor_count: number
}

export interface Investor {
  id: number
  organization_id: number
  investor_code: string
  name: string
  investor_type: string
  region: string
  primary_contact: string
  primary_email: string
  accredited: boolean
  total_committed: number
  active_funds: number
}

export interface Commitment {
  id: number
  fund_id: number
  fund_name: string
  investor_id: number
  investor_name: string
  committed_amount: number
  called_amount: number
  distributed_amount: number
  commitment_date: string
  status: CommitmentStatus
  share_class: string
}

export interface CapitalCall {
  id: number
  fund_id: number
  fund_name: string
  title: string
  due_date: string
  call_date: string
  amount: number
  status: CapitalCallStatus
  paid_pct: number
  investor_count: number
}

export interface Distribution {
  id: number
  fund_id: number
  fund_name: string
  title: string
  distribution_date: string
  record_date: string
  amount: number
  status: DistributionStatus
  paid_pct: number
}

export interface DocumentItem {
  id: number
  document_type: DocumentType
  title: string
  file_name: string
  fund_name?: string
  investor_name?: string
  uploaded_by: string
  file_size: number
  mime_type: string
  is_confidential: boolean
  created_at: string
}

export interface Letter {
  id: number
  fund_name: string
  type: CommunicationType
  subject: string
  excerpt: string
  body: string
  vol: string
  read_minutes: number
  sent_at: string
}

export interface Notification {
  id: number
  title: string
  message: string
  status: "unread" | "read" | "archived"
  related_type: string
  created_at: string
}

export interface Task {
  id: number
  title: string
  fund_name?: string
  assigned_to: string
  status: TaskStatus
  due_date?: string
}

/* ------------------------------------------------------------------ */
/* Firm & user                                                         */
/* ------------------------------------------------------------------ */

export const firm: Organization = {
  id: 1,
  name: "EdenScale",
  legal_name: "EdenScale Partners SCA, SICAV-RAIF",
  type: "fund_manager_firm",
}

export const currentUser = {
  id: 11,
  first_name: "Margot",
  last_name: "Lindqvist",
  email: "m.lindqvist@edenscale.example",
  title: "Director of Investor Relations",
  role: "fund_manager" as const,
}

/* ------------------------------------------------------------------ */
/* Funds                                                               */
/* ------------------------------------------------------------------ */

export const funds: Fund[] = [
  {
    id: 1,
    organization_id: 1,
    name: "Eden Capital VII",
    legal_name: "EdenScale Capital Partners VII, L.P.",
    vintage_year: 2022,
    strategy: "Mid-market private equity, control positions",
    currency_code: "USD",
    target_size: 850_000_000,
    hard_cap: 1_000_000_000,
    current_size: 920_000_000,
    status: "active",
    inception_date: "2022-04-01",
    description:
      "Concentrated fund holding eight to twelve mid-market businesses across Northern Europe and the United States.",
    committed: 920_000_000,
    called: 612_400_000,
    distributed: 184_300_000,
    nav: 1_142_000_000,
    irr: 0.184,
    tvpi: 1.44,
    dpi: 0.2,
    investor_count: 38,
  },
  {
    id: 2,
    organization_id: 1,
    name: "Eden Real Assets III",
    legal_name: "EdenScale Real Assets Partners III, L.P.",
    vintage_year: 2020,
    strategy: "Forestry, infrastructure, working farmland",
    currency_code: "EUR",
    target_size: 600_000_000,
    hard_cap: 750_000_000,
    current_size: 680_000_000,
    status: "active",
    inception_date: "2020-09-15",
    description:
      "Long-duration real-asset programme. Average expected hold of nineteen years.",
    committed: 680_000_000,
    called: 540_900_000,
    distributed: 96_500_000,
    nav: 794_000_000,
    irr: 0.112,
    tvpi: 1.31,
    dpi: 0.142,
    investor_count: 26,
  },
  {
    id: 3,
    organization_id: 1,
    name: "Eden Credit Opportunities II",
    legal_name: "EdenScale Credit Opportunities II, L.P.",
    vintage_year: 2023,
    strategy: "Direct lending to lower-mid-market sponsor-backed borrowers",
    currency_code: "USD",
    target_size: 400_000_000,
    hard_cap: 500_000_000,
    current_size: 312_000_000,
    status: "active",
    inception_date: "2023-06-30",
    description: "Senior secured loans, 6–9 year duration. Quarterly distributions.",
    committed: 312_000_000,
    called: 142_800_000,
    distributed: 11_400_000,
    nav: 154_900_000,
    irr: 0.094,
    tvpi: 1.08,
    dpi: 0.08,
    investor_count: 19,
  },
  {
    id: 4,
    organization_id: 1,
    name: "Eden Capital VI",
    legal_name: "EdenScale Capital Partners VI, L.P.",
    vintage_year: 2017,
    strategy: "Mid-market private equity, control positions",
    currency_code: "USD",
    target_size: 600_000_000,
    hard_cap: 700_000_000,
    current_size: 642_000_000,
    status: "liquidating",
    inception_date: "2017-03-01",
    description:
      "Fully invested. Three remaining holdings in harvest. Final liquidation expected 2027.",
    committed: 642_000_000,
    called: 638_100_000,
    distributed: 1_142_000_000,
    nav: 412_000_000,
    irr: 0.214,
    tvpi: 2.42,
    dpi: 1.79,
    investor_count: 31,
  },
  {
    id: 5,
    organization_id: 1,
    name: "Eden Capital V",
    legal_name: "EdenScale Capital Partners V, L.P.",
    vintage_year: 2012,
    strategy: "Mid-market private equity, control positions",
    currency_code: "USD",
    target_size: 400_000_000,
    hard_cap: 450_000_000,
    current_size: 420_000_000,
    status: "closed",
    inception_date: "2012-09-01",
    description:
      "Realized vintage. Closed in 2024 after twelve years. Final TVPI 2.91x.",
    committed: 420_000_000,
    called: 420_000_000,
    distributed: 1_222_000_000,
    nav: 0,
    irr: 0.198,
    tvpi: 2.91,
    dpi: 2.91,
    investor_count: 28,
  },
]

/* ------------------------------------------------------------------ */
/* Investors                                                           */
/* ------------------------------------------------------------------ */

export const investors: Investor[] = [
  {
    id: 101,
    organization_id: 21,
    investor_code: "LP-0014",
    name: "Lindgren Family Office",
    investor_type: "Single-family office",
    region: "Sweden",
    primary_contact: "Annika Lindgren",
    primary_email: "a.lindgren@lindgrenfamily.example",
    accredited: true,
    total_committed: 92_000_000,
    active_funds: 4,
  },
  {
    id: 102,
    organization_id: 22,
    investor_code: "LP-0027",
    name: "Helvetia Endowment",
    investor_type: "University endowment",
    region: "Switzerland",
    primary_contact: "Dr Tobias Wenger",
    primary_email: "t.wenger@helvetia-edu.example",
    accredited: true,
    total_committed: 145_000_000,
    active_funds: 3,
  },
  {
    id: 103,
    organization_id: 23,
    investor_code: "LP-0031",
    name: "Coastal States Pension",
    investor_type: "Public pension",
    region: "United States",
    primary_contact: "Marcus Pell",
    primary_email: "mpell@coastalstates.example",
    accredited: true,
    total_committed: 220_000_000,
    active_funds: 2,
  },
  {
    id: 104,
    organization_id: 24,
    investor_code: "LP-0042",
    name: "Albrecht Stiftung",
    investor_type: "Foundation",
    region: "Germany",
    primary_contact: "Petra Albrecht",
    primary_email: "petra@albrecht-stiftung.example",
    accredited: true,
    total_committed: 64_500_000,
    active_funds: 3,
  },
  {
    id: 105,
    organization_id: 25,
    investor_code: "LP-0048",
    name: "Whitcombe & Sons Trust",
    investor_type: "Family trust",
    region: "United Kingdom",
    primary_contact: "Edmund Whitcombe",
    primary_email: "e.whitcombe@whitcombe.example",
    accredited: true,
    total_committed: 48_000_000,
    active_funds: 2,
  },
  {
    id: 106,
    organization_id: 26,
    investor_code: "LP-0055",
    name: "Tanaka Holdings",
    investor_type: "Multi-family office",
    region: "Japan",
    primary_contact: "Hideo Tanaka",
    primary_email: "h.tanaka@tanaka-holdings.example",
    accredited: true,
    total_committed: 78_000_000,
    active_funds: 2,
  },
  {
    id: 107,
    organization_id: 27,
    investor_code: "LP-0061",
    name: "Mirakel Pensjonskasse",
    investor_type: "Corporate pension",
    region: "Norway",
    primary_contact: "Solveig Berg",
    primary_email: "s.berg@mirakel.example",
    accredited: true,
    total_committed: 130_000_000,
    active_funds: 2,
  },
  {
    id: 108,
    organization_id: 28,
    investor_code: "LP-0068",
    name: "Brennan Capital LLC",
    investor_type: "Single-family office",
    region: "United States",
    primary_contact: "Jane Brennan",
    primary_email: "jane@brennancap.example",
    accredited: true,
    total_committed: 36_000_000,
    active_funds: 1,
  },
]

/* ------------------------------------------------------------------ */
/* Commitments                                                         */
/* ------------------------------------------------------------------ */

export const commitments: Commitment[] = [
  {
    id: 1,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    investor_id: 101,
    investor_name: "Lindgren Family Office",
    committed_amount: 25_000_000,
    called_amount: 16_625_000,
    distributed_amount: 5_000_000,
    commitment_date: "2022-06-01",
    status: "approved",
    share_class: "A",
  },
  {
    id: 2,
    fund_id: 2,
    fund_name: "Eden Real Assets III",
    investor_id: 101,
    investor_name: "Lindgren Family Office",
    committed_amount: 30_000_000,
    called_amount: 23_850_000,
    distributed_amount: 4_300_000,
    commitment_date: "2020-11-12",
    status: "approved",
    share_class: "A",
  },
  {
    id: 3,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    investor_id: 102,
    investor_name: "Helvetia Endowment",
    committed_amount: 60_000_000,
    called_amount: 39_900_000,
    distributed_amount: 12_000_000,
    commitment_date: "2022-04-25",
    status: "approved",
    share_class: "A",
  },
  {
    id: 4,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    investor_id: 103,
    investor_name: "Coastal States Pension",
    committed_amount: 100_000_000,
    called_amount: 66_500_000,
    distributed_amount: 20_000_000,
    commitment_date: "2022-05-04",
    status: "approved",
    share_class: "A",
  },
  {
    id: 5,
    fund_id: 3,
    fund_name: "Eden Credit Opportunities II",
    investor_id: 107,
    investor_name: "Mirakel Pensjonskasse",
    committed_amount: 50_000_000,
    called_amount: 22_900_000,
    distributed_amount: 1_800_000,
    commitment_date: "2023-08-19",
    status: "approved",
    share_class: "A",
  },
  {
    id: 6,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    investor_id: 108,
    investor_name: "Brennan Capital LLC",
    committed_amount: 15_000_000,
    called_amount: 0,
    distributed_amount: 0,
    commitment_date: "2026-04-12",
    status: "pending",
    share_class: "A",
  },
]

/* ------------------------------------------------------------------ */
/* Capital calls                                                       */
/* ------------------------------------------------------------------ */

export const capitalCalls: CapitalCall[] = [
  {
    id: 1,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    title: "Capital call no. 9 — Aurelia Industrial follow-on",
    due_date: "2026-05-15",
    call_date: "2026-04-22",
    amount: 38_400_000,
    status: "sent",
    paid_pct: 0.42,
    investor_count: 38,
  },
  {
    id: 2,
    fund_id: 2,
    fund_name: "Eden Real Assets III",
    title: "Capital call no. 12 — Linnér forestry expansion",
    due_date: "2026-05-30",
    call_date: "2026-04-28",
    amount: 24_500_000,
    status: "scheduled",
    paid_pct: 0,
    investor_count: 26,
  },
  {
    id: 3,
    fund_id: 3,
    fund_name: "Eden Credit Opportunities II",
    title: "Capital call no. 4 — New origination tranche",
    due_date: "2026-04-25",
    call_date: "2026-04-04",
    amount: 18_900_000,
    status: "overdue",
    paid_pct: 0.71,
    investor_count: 19,
  },
  {
    id: 4,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    title: "Capital call no. 8 — Vasari Editions acquisition",
    due_date: "2026-02-10",
    call_date: "2026-01-21",
    amount: 52_200_000,
    status: "paid",
    paid_pct: 1.0,
    investor_count: 38,
  },
  {
    id: 5,
    fund_id: 2,
    fund_name: "Eden Real Assets III",
    title: "Capital call no. 11 — Iberian water utility",
    due_date: "2025-11-30",
    call_date: "2025-11-08",
    amount: 31_000_000,
    status: "paid",
    paid_pct: 1.0,
    investor_count: 26,
  },
  {
    id: 6,
    fund_id: 1,
    fund_name: "Eden Capital VII",
    title: "Capital call no. 7 — General partnership expenses",
    due_date: "2025-09-30",
    call_date: "2025-09-09",
    amount: 4_800_000,
    status: "paid",
    paid_pct: 1.0,
    investor_count: 38,
  },
]

/* ------------------------------------------------------------------ */
/* Distributions                                                       */
/* ------------------------------------------------------------------ */

export const distributions: Distribution[] = [
  {
    id: 1,
    fund_id: 4,
    fund_name: "Eden Capital VI",
    title: "Distribution no. 14 — Calder Credit partial exit",
    distribution_date: "2026-04-30",
    record_date: "2026-04-10",
    amount: 84_500_000,
    status: "scheduled",
    paid_pct: 0,
  },
  {
    id: 2,
    fund_id: 4,
    fund_name: "Eden Capital VI",
    title: "Distribution no. 13 — Arvada Holdings recap",
    distribution_date: "2026-01-30",
    record_date: "2026-01-10",
    amount: 142_000_000,
    status: "paid",
    paid_pct: 1.0,
  },
  {
    id: 3,
    fund_id: 5,
    fund_name: "Eden Capital V",
    title: "Final distribution — fund wind-up",
    distribution_date: "2025-09-15",
    record_date: "2025-09-01",
    amount: 92_400_000,
    status: "paid",
    paid_pct: 1.0,
  },
  {
    id: 4,
    fund_id: 2,
    fund_name: "Eden Real Assets III",
    title: "Distribution no. 4 — Forestry harvest income",
    distribution_date: "2025-12-15",
    record_date: "2025-11-30",
    amount: 28_600_000,
    status: "paid",
    paid_pct: 1.0,
  },
  {
    id: 5,
    fund_id: 3,
    fund_name: "Eden Credit Opportunities II",
    title: "Quarterly coupon distribution Q1",
    distribution_date: "2026-03-31",
    record_date: "2026-03-15",
    amount: 5_400_000,
    status: "paid",
    paid_pct: 1.0,
  },
]

/* ------------------------------------------------------------------ */
/* Documents                                                           */
/* ------------------------------------------------------------------ */

export const documents: DocumentItem[] = [
  {
    id: 1,
    document_type: "report",
    title: "Eden Capital VII — Q1 2026 quarterly report",
    file_name: "ECVII-Q1-2026-quarterly-report.pdf",
    fund_name: "Eden Capital VII",
    uploaded_by: "Margot Lindqvist",
    file_size: 4_842_000,
    mime_type: "application/pdf",
    is_confidential: true,
    created_at: "2026-04-15",
  },
  {
    id: 2,
    document_type: "financial",
    title: "Eden Capital VII — Audited financial statements 2025",
    file_name: "ECVII-2025-audited.pdf",
    fund_name: "Eden Capital VII",
    uploaded_by: "Sebastian Holm",
    file_size: 3_217_000,
    mime_type: "application/pdf",
    is_confidential: true,
    created_at: "2026-03-22",
  },
  {
    id: 3,
    document_type: "notice",
    title: "Capital call no. 9 notice — Eden Capital VII",
    file_name: "ECVII-call-09-notice.pdf",
    fund_name: "Eden Capital VII",
    uploaded_by: "Margot Lindqvist",
    file_size: 412_000,
    mime_type: "application/pdf",
    is_confidential: true,
    created_at: "2026-04-22",
  },
  {
    id: 4,
    document_type: "legal",
    title: "Limited partnership agreement — Eden Credit Opportunities II",
    file_name: "ECO-II-LPA-executed.pdf",
    fund_name: "Eden Credit Opportunities II",
    uploaded_by: "Counsel",
    file_size: 7_823_000,
    mime_type: "application/pdf",
    is_confidential: true,
    created_at: "2023-06-30",
  },
  {
    id: 5,
    document_type: "kyc_aml",
    title: "KYC pack — Brennan Capital LLC",
    file_name: "brennan-capital-kyc.zip",
    investor_name: "Brennan Capital LLC",
    uploaded_by: "Compliance team",
    file_size: 12_400_000,
    mime_type: "application/zip",
    is_confidential: true,
    created_at: "2026-04-12",
  },
  {
    id: 6,
    document_type: "report",
    title: "Eden Real Assets III — Q4 2025 portfolio update",
    file_name: "ERA-III-Q4-2025-update.pdf",
    fund_name: "Eden Real Assets III",
    uploaded_by: "Margot Lindqvist",
    file_size: 2_902_000,
    mime_type: "application/pdf",
    is_confidential: true,
    created_at: "2026-02-12",
  },
  {
    id: 7,
    document_type: "other",
    title: "ESG framework — 2026 update",
    file_name: "edenscale-esg-2026.pdf",
    uploaded_by: "Margot Lindqvist",
    file_size: 1_140_000,
    mime_type: "application/pdf",
    is_confidential: false,
    created_at: "2026-01-30",
  },
]

/* ------------------------------------------------------------------ */
/* Letters / communications                                            */
/* ------------------------------------------------------------------ */

export const letters: Letter[] = [
  {
    id: 1,
    fund_name: "Eden Capital VII",
    type: "announcement",
    subject: "On the discipline of holding cash when the room is loud",
    excerpt:
      "We did not deploy in March. The bid was rich and the seller was patient — a combination that almost always favours waiting.",
    body: "",
    vol: "Vol. xii · No. 3",
    read_minutes: 8,
    sent_at: "2026-04-15",
  },
  {
    id: 2,
    fund_name: "Eden Real Assets III",
    type: "announcement",
    subject: "Forestry, fifty years on: notes from the Linnér holding",
    excerpt:
      "A standing forest is the longest-duration asset most investors will ever hold. After five years, we are starting to understand what we own.",
    body: "",
    vol: "Vol. xii · No. 2",
    read_minutes: 12,
    sent_at: "2026-01-15",
  },
  {
    id: 3,
    fund_name: "EdenScale",
    type: "announcement",
    subject: "Why we said no to twenty-eight things this quarter",
    excerpt:
      "Concentrated portfolios are made by what one declines, not what one buys. A short reckoning of the year's near-misses.",
    body: "",
    vol: "Vol. xii · No. 1",
    read_minutes: 6,
    sent_at: "2025-10-15",
  },
  {
    id: 4,
    fund_name: "Eden Capital VI",
    type: "notification",
    subject: "Final harvest schedule — Eden Capital VI",
    excerpt:
      "Three remaining holdings, expected liquidation 2027. We do not anticipate further capital calls.",
    body: "",
    vol: "Vol. xi · No. 4",
    read_minutes: 4,
    sent_at: "2025-07-20",
  },
]

/* ------------------------------------------------------------------ */
/* Notifications & tasks                                               */
/* ------------------------------------------------------------------ */

export const notifications: Notification[] = [
  {
    id: 1,
    title: "Capital call no. 9 issued",
    message:
      "Eden Capital VII — $38.4M called from 38 limited partners. Due 15 May 2026.",
    status: "unread",
    related_type: "capital_call",
    created_at: "2026-04-22",
  },
  {
    id: 2,
    title: "Brennan Capital LLC — KYC pack uploaded",
    message:
      "Compliance team uploaded the KYC pack. Awaiting review before approval.",
    status: "unread",
    related_type: "investor",
    created_at: "2026-04-12",
  },
  {
    id: 3,
    title: "Q1 2026 quarterly report distributed",
    message:
      "Eden Capital VII Q1 report sent to 38 limited partners. 27 have opened it.",
    status: "read",
    related_type: "document",
    created_at: "2026-04-15",
  },
  {
    id: 4,
    title: "Distribution no. 14 scheduled",
    message:
      "Eden Capital VI — $84.5M scheduled for 30 April 2026 from Calder Credit partial exit.",
    status: "read",
    related_type: "distribution",
    created_at: "2026-04-10",
  },
]

export const tasks: Task[] = [
  {
    id: 1,
    title: "Review and approve Brennan Capital subscription documents",
    fund_name: "Eden Capital VII",
    assigned_to: "Margot Lindqvist",
    status: "open",
    due_date: "2026-05-02",
  },
  {
    id: 2,
    title: "Counter-sign Lindgren side letter amendment",
    fund_name: "Eden Real Assets III",
    assigned_to: "Margot Lindqvist",
    status: "in_progress",
    due_date: "2026-05-05",
  },
  {
    id: 3,
    title: "Schedule Q2 LP advisory committee meeting",
    fund_name: "Eden Capital VII",
    assigned_to: "Sebastian Holm",
    status: "open",
    due_date: "2026-05-10",
  },
  {
    id: 4,
    title: "Reconcile Q1 capital account statements",
    assigned_to: "Finance team",
    status: "in_progress",
    due_date: "2026-04-30",
  },
]

/* ------------------------------------------------------------------ */
/* Aggregates                                                          */
/* ------------------------------------------------------------------ */

export function getFirmAggregates() {
  const activeFunds = funds.filter((f) => f.status === "active")
  const totalCommitted = funds.reduce((acc, f) => acc + f.committed, 0)
  const totalCalled = funds.reduce((acc, f) => acc + f.called, 0)
  const totalDistributed = funds.reduce((acc, f) => acc + f.distributed, 0)
  const totalNav = funds.reduce((acc, f) => acc + f.nav, 0)
  return {
    activeFundCount: activeFunds.length,
    fundCount: funds.length,
    totalCommitted,
    totalCalled,
    totalDistributed,
    totalNav,
    investorCount: investors.length,
    dryPowder: totalCommitted - totalCalled,
  }
}
