// Builds and assembles the newtaven.com static asset tree:
//   /       <- apps/web/dist       (marketing, Astro)
//   /app/*  <- apps/frontend/dist  (product SPA, built with base=/app/)
//
// Builds apps/web and apps/frontend itself (this repo has no turbo/pnpm-workspace
// pipeline to do it for us) so that production-only env vars — e.g.
//   VITE_API_URL=https://api.newtaven.com VITE_HANKO_API_URL=... pnpm run build
// — reach the actual `vite build` invocation. Vite bakes VITE_* vars in at
// build time, so they must be set in the env of *this* process, not just
// exported around a prior, separate frontend build.
import { cp, rm } from "node:fs/promises"
import { execSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

const here = dirname(fileURLToPath(import.meta.url))
const distDir = resolve(here, "../dist")
const webDir = resolve(here, "../../web")
const frontendDir = resolve(here, "../../frontend")

for (const [label, dir, cmd] of [
  ["apps/web", webDir, "npm run build"],
  ["apps/frontend", frontendDir, "pnpm run build"],
]) {
  console.log(`> ${label}: ${cmd}`)
  execSync(cmd, { cwd: dir, stdio: "inherit", env: process.env })
}

await rm(distDir, { recursive: true, force: true })
await cp(resolve(webDir, "dist"), distDir, { recursive: true })
await cp(resolve(frontendDir, "dist"), resolve(distDir, "app"), { recursive: true })
console.log("assembled gateway dist <- web(/) + frontend(/app)")
