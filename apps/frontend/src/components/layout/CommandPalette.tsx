import { useNavigate } from "react-router-dom"
import {
  FileText,
  Layers,
  LogOut,
  Mail,
  User as UserIcon,
  Users,
} from "lucide-react"

import { useApiQuery } from "@/hooks/useApiQuery"
import { useAuth } from "@/hooks/useAuth"
import { useNavItems } from "@/hooks/useNavItems"
import { Skeleton } from "@/components/ui/skeleton"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (next: boolean) => void
}

const STALE_FIVE_MIN = 5 * 60 * 1000

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  legal: "Legal",
  kyc_aml: "KYC / AML",
  financial: "Financial",
  report: "Report",
  notice: "Notice",
  other: "Other",
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { logout } = useAuth()
  const { items: navItems } = useNavItems()

  const fundsQuery = useApiQuery("/funds", undefined, {
    enabled: open,
    staleTime: STALE_FIVE_MIN,
  })
  const investorsQuery = useApiQuery("/investors", undefined, {
    enabled: open,
    staleTime: STALE_FIVE_MIN,
  })
  const documentsQuery = useApiQuery(
    "/documents",
    { params: { query: { limit: 50 } } },
    { enabled: open, staleTime: STALE_FIVE_MIN },
  )

  const close = () => onOpenChange(false)

  const run = (fn: () => void) => () => {
    close()
    fn()
  }

  const handleSignOut = run(async () => {
    await logout()
    navigate("/login")
  })

  const isLoading =
    fundsQuery.isLoading ||
    investorsQuery.isLoading ||
    documentsQuery.isLoading

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Search"
      description="Search funds, investors, documents and jump to any page."
    >
      <CommandInput placeholder="Search funds, investors, documents…" />
      <CommandList>
        <CommandEmpty>No matches</CommandEmpty>

        <CommandGroup heading="Quick actions">
          {navItems
            .filter(
              (entry): entry is Extract<typeof entry, { to: string }> =>
                entry.kind !== "section" && entry.kind !== "divider",
            )
            .map(({ to, label, icon: Icon }) => (
              <CommandItem
                key={`nav-${to}`}
                value={`go ${label} ${to}`}
                onSelect={run(() => navigate(to))}
              >
                <Icon strokeWidth={1.5} />
                <span>Go to {label}</span>
              </CommandItem>
            ))}
          <CommandItem
            value="profile account"
            onSelect={run(() => navigate("/profile"))}
          >
            <UserIcon strokeWidth={1.5} />
            <span>Go to Profile</span>
          </CommandItem>
          <CommandItem
            value="sign out logout log out"
            onSelect={handleSignOut}
          >
            <LogOut strokeWidth={1.5} />
            <span>Sign out</span>
          </CommandItem>
        </CommandGroup>

        {isLoading ? (
          <CommandGroup heading="Loading">
            <div className="space-y-2 px-2 py-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-5/6" />
              <Skeleton className="h-8 w-2/3" />
            </div>
          </CommandGroup>
        ) : null}

        {fundsQuery.data && fundsQuery.data.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Funds">
              {fundsQuery.data.map((fund) => (
                <CommandItem
                  key={`fund-${fund.id}`}
                  value={`fund ${fund.name} ${fund.vintage_year ?? ""}`}
                  onSelect={run(() => navigate(`/funds/${fund.id}`))}
                >
                  <Layers strokeWidth={1.5} />
                  <span className="truncate">{fund.name}</span>
                  {fund.vintage_year != null ? (
                    <CommandShortcut>{fund.vintage_year}</CommandShortcut>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}

        {investorsQuery.data && investorsQuery.data.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Investors">
              {investorsQuery.data.map((investor) => (
                <CommandItem
                  key={`investor-${investor.id}`}
                  value={`investor ${investor.name} ${investor.investor_code ?? ""}`}
                  onSelect={run(() => navigate("/investors"))}
                >
                  <Users strokeWidth={1.5} />
                  <span className="truncate">{investor.name}</span>
                  {investor.investor_code ? (
                    <CommandShortcut>{investor.investor_code}</CommandShortcut>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}

        {documentsQuery.data && documentsQuery.data.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Documents">
              {documentsQuery.data.map((doc) => {
                const Icon =
                  doc.document_type === "notice" ? Mail : FileText
                const typeLabel =
                  DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type
                return (
                  <CommandItem
                    key={`doc-${doc.id}`}
                    value={`document ${doc.title} ${doc.file_name} ${typeLabel}`}
                    onSelect={run(() => navigate("/documents"))}
                  >
                    <Icon strokeWidth={1.5} />
                    <span className="truncate">{doc.title}</span>
                    <CommandShortcut>{typeLabel}</CommandShortcut>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </>
        ) : null}
      </CommandList>
    </CommandDialog>
  )
}
