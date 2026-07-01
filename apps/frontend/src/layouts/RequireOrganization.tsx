import { Navigate, Outlet } from "react-router-dom"
import { useActiveOrganization } from "@/hooks/useActiveOrganization"

export default function RequireOrganization() {
  const { memberships, isSuperadmin } = useActiveOrganization()
  const hasOrgAccess = memberships.length > 0 || isSuperadmin

  if (!hasOrgAccess) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
