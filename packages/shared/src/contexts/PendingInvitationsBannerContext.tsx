import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

export interface PendingInvitationsBannerContextValue {
  bannerDismissed: boolean
  dismissBanner: () => void
  declinedIds: ReadonlySet<string>
  decline: (invitationId: string) => void
}

const PendingInvitationsBannerContext =
  createContext<PendingInvitationsBannerContextValue | null>(null)

interface ProviderProps {
  children: ReactNode
}

export function PendingInvitationsBannerProvider({ children }: ProviderProps) {
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const [declinedIds, setDeclinedIds] = useState<Set<string>>(() => new Set())

  const dismissBanner = useCallback(() => {
    setBannerDismissed(true)
  }, [])

  const decline = useCallback((invitationId: string) => {
    setDeclinedIds((prev) => {
      if (prev.has(invitationId)) return prev
      const next = new Set(prev)
      next.add(invitationId)
      return next
    })
  }, [])

  const value = useMemo<PendingInvitationsBannerContextValue>(
    () => ({ bannerDismissed, dismissBanner, declinedIds, decline }),
    [bannerDismissed, dismissBanner, declinedIds, decline],
  )

  return (
    <PendingInvitationsBannerContext.Provider value={value}>
      {children}
    </PendingInvitationsBannerContext.Provider>
  )
}

export function usePendingInvitationsBanner(): PendingInvitationsBannerContextValue {
  const ctx = useContext(PendingInvitationsBannerContext)
  if (!ctx) {
    throw new Error(
      "usePendingInvitationsBanner must be used within a PendingInvitationsBannerProvider",
    )
  }
  return ctx
}
