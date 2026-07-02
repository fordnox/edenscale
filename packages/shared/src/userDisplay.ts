export function deriveInitials(
  first?: string | null,
  last?: string | null,
  email?: string | null,
) {
  const f = (first ?? "").trim()
  const l = (last ?? "").trim()
  if (f && l) return (f[0] + l[0]).toUpperCase()
  if (f.length >= 2) return f.slice(0, 2).toUpperCase()
  const local = (email ?? "").split("@")[0] ?? ""
  const parts = local.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (local.slice(0, 2) || "ES").toUpperCase()
}
