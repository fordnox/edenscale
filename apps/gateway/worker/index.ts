interface Env {
  ASSETS: Fetcher
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)

    const appMount =
      url.pathname === "/manager" || url.pathname.startsWith("/manager/")
        ? "/manager"
        : url.pathname === "/investor" || url.pathname.startsWith("/investor/")
          ? "/investor"
          : null

    // Product SPAs mounted at /manager/ and /investor/ — serve the asset,
    // falling back to the SPA shell for client-side document navigations.
    if (appMount) {
      const res = await env.ASSETS.fetch(request)
      if (res.status === 404 || (res.status >= 300 && res.status < 400)) {
        // Only navigations (deep links like /manager/acme/funds) fall back to the
        // SPA shell. A missing hashed asset — e.g. a stale cached index.html
        // requesting an old JS chunk after a redeploy pruned it — must return
        // the real 404, NOT the HTML shell. Serving index.html for a
        // `<script type=module>` request makes the browser reject it with a
        // MIME-type error ("Expected a JavaScript module … got text/html").
        const dest = request.headers.get("Sec-Fetch-Dest")
        const accept = request.headers.get("Accept") || ""
        const isNavigation =
          dest === "document" || (!dest && accept.includes("text/html"))
        if (isNavigation) {
          return env.ASSETS.fetch(new URL(`${appMount}/index.html`, url.origin))
        }
      }
      return res
    }

    // Marketing site (/) is served directly by the asset layer; this
    // fallthrough only runs if the worker is invoked for it.
    return env.ASSETS.fetch(request)
  },
} satisfies ExportedHandler<Env>
