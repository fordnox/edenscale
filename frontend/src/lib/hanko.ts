import { Hanko } from "@teamhanko/hanko-elements"
import { config } from "@/lib/config"

export const hanko = new Hanko(config.VITE_HANKO_API_URL)

export function getSessionToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)hanko=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}
