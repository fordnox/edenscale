// Shared site metadata for the static sites (apps/web, apps/docs) and the
// gateway. Path mounts must match apps/gateway/scripts/assemble.mjs and
// worker/index.ts.

export const SITE = {
  name: "NewTaven",
  domain: "newtaven.com",
  url: "https://newtaven.com",
  /** Path prefixes the gateway serves each app under. */
  paths: {
    marketing: "/",
    docs: "/docs",
    manager: "/manager",
    investor: "/investor",
    superadmin: "/superadmin",
  },
};
