// Assembles the newtaven.com static asset tree:
//   /       <- apps/web/dist       (marketing, Astro)
//   /app/*  <- apps/frontend/dist  (product SPA, built with base=/app/)
// Assumes @gtlane/web and @gtlane/frontend are already built (run their
// `build` scripts first — this repo has no turbo/pnpm-workspace pipeline
// to guarantee ordering automatically).
import { cp, rm, access } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

const here = dirname(fileURLToPath(import.meta.url))
const distDir = resolve(here, "../dist")
const webDist = resolve(here, "../../web/dist")
const frontendDist = resolve(here, "../../frontend/dist")

for (const [label, dir] of [
  ["apps/web", webDist],
  ["apps/frontend", frontendDist],
]) {
  await access(dir).catch(() => {
    throw new Error(`Missing ${dir} — build ${label} first.`)
  })
}

await rm(distDir, { recursive: true, force: true })
await cp(webDist, distDir, { recursive: true })
await cp(frontendDist, resolve(distDir, "app"), { recursive: true })
console.log("assembled gateway dist <- web(/) + frontend(/app)")
