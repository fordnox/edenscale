// Builds and assembles the newtaven.com static asset tree:
//   /             <- apps/web/dist        (marketing, Astro)
//   /manager/*    <- apps/manager/dist    (manager SPA)
//   /investor/*   <- apps/investor/dist   (investor SPA)
//   /superadmin/* <- apps/superadmin/dist (superadmin SPA)
//   /docs/*       <- apps/docs/dist       (docs, Astro/Starlight)
import { cp, rm } from "node:fs/promises"
import { execSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

const here = dirname(fileURLToPath(import.meta.url))
const rootDir = resolve(here, "../../..")
const distDir = resolve(here, "../dist")
const webDir = resolve(here, "../../web")
const managerDir = resolve(here, "../../manager")
const investorDir = resolve(here, "../../investor")
const superadminDir = resolve(here, "../../superadmin")
const docsDir = resolve(here, "../../docs")

const cmd =
  "pnpm turbo run build --filter=web --filter=manager --filter=investor --filter=superadmin --filter=docs"
console.log(`> root: ${cmd}`)
execSync(cmd, { cwd: rootDir, stdio: "inherit", env: process.env })

await rm(distDir, { recursive: true, force: true })
await cp(resolve(webDir, "dist"), distDir, { recursive: true })
await cp(resolve(managerDir, "dist"), resolve(distDir, "manager"), { recursive: true })
await cp(resolve(investorDir, "dist"), resolve(distDir, "investor"), { recursive: true })
await cp(resolve(superadminDir, "dist"), resolve(distDir, "superadmin"), { recursive: true })
await cp(resolve(docsDir, "dist"), resolve(distDir, "docs"), { recursive: true })
console.log(
  "assembled gateway dist <- web(/) + manager(/manager) + investor(/investor) + superadmin(/superadmin) + docs(/docs)",
)
