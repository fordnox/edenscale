import { Loader2 } from "lucide-react"

import AppShell from "@/layouts/AppShell"
import NoOrganizationLayout from "@/layouts/NoOrganizationLayout"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"

export default function DashboardShell() {
  const { memberships, isSuperadmin, isLoading } = useActiveOrganization()

  if (isLoading) {
    return (
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </main>
    )
  }

  const hasOrgAccess = memberships.length > 0 || isSuperadmin

  return hasOrgAccess ? <AppShell /> : <NoOrganizationLayout />
}
