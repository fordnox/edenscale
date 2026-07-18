# Email Ingestion Worker — Implementation Plan

Cloudflare Worker that receives email sent to `ingest@newtaven.com` (and
`ingest+<org-slug>@newtaven.com`), extracts the attachments, and stores them as
`Document` rows in the NewTaven backend.

## Overview

```
Sender ──► ingest@newtaven.com  |  ingest+<org-slug>@newtaven.com
              │  (Cloudflare Email Routing catch-all rule, MX on newtaven.com)
              ▼
        newtaven-email-ingest  (this Worker: email() handler)
              │  1. buffer message.raw (single-use)
              │  2. PostalMime.parse → attachments[]
              │  3. drop inline/CID parts (logos, signatures)
              │  4. POST base64 attachments + sender + recipient to backend
              ▼
        POST {BACKEND_URL}/email-ingest/documents
        header: X-Email-Ingest-Token: <shared secret>
              │
              ▼
        Backend resolves target org (recipient +tag, else sender's sole
        eligible org), writes bytes via storage service, creates Documents.
```

**Decisions already made (do not re-litigate):**
- Routing target = **plus-addressing with a sender-email fallback**. A
  `+<org-slug>` tag on the recipient (`ingest+acme@`) selects the org; the sender
  must hold an `admin`/`fund_manager` membership there. Without a tag, a sender
  with exactly one eligible org resolves to it; multiple → drop with a hint to
  use the tagged address. An invalid/unauthorized tag never falls back.
- Unauthorized/unknown/ambiguous sender = **drop silently**, but always `console.log` the outcome so drops are traceable in Worker logs (`observability` on).
- Worker is **separate** from `newtaven-gateway` (gateway stays a pure static-asset worker).

## Directory layout

```
apps/email-ingest/
├── PLAN.md              ← this file
├── package.json
├── tsconfig.json
├── wrangler.json
└── worker/
    └── index.ts         ← email() handler
```

## Files

### `package.json`
```jsonc
{
  "name": "email-ingest",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "lint": "tsc --noEmit",
    "deploy": "wrangler deploy"
  },
  "dependencies": {
    "postal-mime": "^2.4.4"        // MIME parser (attachments)
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20260508.1",
    "typescript": "^6.0.2",
    "wrangler": "^4.90.0"
  }
}
```
Mirror versions used by `apps/gateway`. Only new runtime dep is `postal-mime`.

### `wrangler.json`
```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "newtaven-email-ingest",
  "main": "./worker/index.ts",
  "compatibility_date": "2026-05-07",
  "compatibility_flags": ["nodejs_compat"],   // postal-mime needs Node built-ins
  "workers_dev": false,
  "observability": { "enabled": true },
  "vars": {
    "BACKEND_URL": "https://api.newtaven.com"  // backend origin (no trailing slash)
  }
  // NO routes / custom_domain: the Email Routing rule binds this Worker.
  // Secret EMAIL_INGEST_TOKEN set via `wrangler secret put` (not in file).
}
```

### `worker/index.ts`

**Implemented** — see the actual file `worker/index.ts` (this snippet mirrors it).
Passing `attachmentEncoding: "base64"` to `PostalMime.parse` returns each
attachment's `content` as a base64 string directly, so no manual byte→base64
conversion is needed.

```typescript
import PostalMime from "postal-mime";

interface Env {
  BACKEND_URL: string;
  EMAIL_INGEST_TOKEN: string;   // secret
}

export default {
  async email(message, env, ctx): Promise<void> {
    const from = message.from;                     // trustworthy envelope sender
    const to = message.to;

    // 1. Buffer raw ONCE (single-use stream), then parse as base64 attachments.
    const raw = await new Response(message.raw).arrayBuffer();
    const parsed = await PostalMime.parse(raw, { attachmentEncoding: "base64" });

    // 2. Keep only real file attachments; drop inline / related CID parts
    //    (logos, signatures) and anything with no content.
    const attachments = (parsed.attachments ?? [])
      .filter((a) =>
        a.disposition !== "inline" &&
        a.related !== true &&
        typeof a.content === "string" &&
        a.content.length > 0,
      )
      .map((a) => ({
        file_name: a.filename || "attachment",
        mime_type: a.mimeType || "application/octet-stream",
        content_base64: a.content as string,
      }));

    if (attachments.length === 0) {
      console.log(`[email-ingest] drop: no attachments from=${from} to=${to}`);
      return; // raw already consumed → clean drop
    }

    // 3. POST to backend. Backend decides authorization + org resolution and
    //    returns a drop reason (still 200) for unknown/ambiguous senders.
    try {
      const res = await fetch(`${env.BACKEND_URL}/email-ingest/documents`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-email-ingest-token": env.EMAIL_INGEST_TOKEN,
        },
        body: JSON.stringify({
          sender_email: from,
          subject: parsed.subject ?? "",
          attachments,
        }),
      });
      const body = await res.text();
      console.log(
        `[email-ingest] from=${from} to=${to} attachments=${attachments.length} ` +
        `status=${res.status} resp=${body.slice(0, 300)}`,
      );
    } catch (err) {
      console.log(`[email-ingest] error posting from=${from}: ${String(err)}`);
    }
    // No setReject / no forward → silent drop on any failure, per decision.
  },
} satisfies ExportedHandler<Env>;
```

Confirmed `postal-mime` v2 `Attachment` shape (via library docs):
`{ filename: string | null, mimeType, disposition: "attachment" | "inline" | null,
related?: boolean, contentId?: string, content, encoding? }`. With
`attachmentEncoding: "base64"`, `content` is a base64 `string`.

### `tsconfig.json`
Copy `apps/gateway/tsconfig.json` (ES2023, `moduleResolution: bundler`, strict,
`@cloudflare/workers-types`).

## Backend contract this Worker depends on

New endpoint (built alongside — separate backend task, summarized here so the
Worker contract is unambiguous):

- `POST /email-ingest/documents`
- Auth: header `X-Email-Ingest-Token` compared (constant-time) to
  `settings.EMAIL_INGEST_TOKEN`. Missing/empty setting ⇒ feature disabled (404).
  Mismatch ⇒ 403.
- Request JSON:
  ```json
  {
    "sender_email": "jane@acmecapital.com",
    "subject": "Q3 report",
    "attachments": [
      { "file_name": "q3.pdf", "mime_type": "application/pdf", "content_base64": "..." }
    ]
  }
  ```
  (plus `"recipient": "ingest+acme@newtaven.com"` — the `+<org-slug>` tag.)
- Behavior: resolve `sender_email` → `User`; resolve the org from the
  recipient's `+<org-slug>` tag (sender must be an `admin`/`fund_manager` there),
  else fall back to the sender's sole eligible membership. For each attachment:
  `storage.write(...)` then `DocumentRepository.create(...)` with
  `document_type=other`, `title = subject || file_name`, `is_confidential=true`,
  `uploaded_by_user_id = user.id`. Fires `notify_document_uploaded`.
- Response: always `200` with `{ "status": "created" | "dropped", ... }`
  (drops are not errors — the Worker just logs them).

## Turborepo / workspace wiring

- `apps/email-ingest` is picked up by `pnpm-workspace.yaml` (`apps/*`) — no change.
- Add to `.gitignore` patterns if a build dir appears (Wrangler bundles in place,
  so likely none).
- `make openapi` regenerates the client after the backend endpoint lands (the
  Worker doesn't use the generated client, but the endpoint must be in the schema).

## Ops / one-time setup (run by a human, documented here)

1. **Enable Email Routing** on `newtaven.com` (Dashboard → Email Service → Email
   Routing, or `wrangler email routing enable`). This publishes the MX records.
2. **Deploy the Worker:** `cd apps/email-ingest && pnpm run deploy`.
3. **Route inbound mail to the Worker.** Addresses are `ingest@newtaven.com`
   (single-org senders) and `ingest+<org-slug>@newtaven.com` (explicit org).
   Plus-tagged sub-addresses are NOT individually creatable, so route them via a
   **catch-all** rule to the Worker:
   ```
   wrangler email routing rules catch-all update --worker newtaven-email-ingest
   ```
   (or Dashboard → Email Routing → Catch-all address → Send to Worker). The
   Worker/backend simply drop mail with no attachments or an unresolvable
   sender/org, so catch-all is safe — but the handler may optionally ignore any
   local-part whose base isn't `ingest`.
4. **Set the shared secret (same value both sides):**
   ```
   cd apps/email-ingest && wrangler secret put EMAIL_INGEST_TOKEN
   ```
   and set `EMAIL_INGEST_TOKEN` in the backend env (Kamal / 1Password).

## Testing

- **Local Worker:** `wrangler dev` can't receive real email; test `email()` with
  `wrangler`'s email test harness or by invoking the handler from a unit test with
  a mock `ForwardableEmailMessage` (mock `raw` as a stream over a fixture `.eml`).
- **End-to-end:** after routing rule + secret, send a real email with a PDF from a
  known admin user's address; confirm the document appears in the manager app and
  a `document_uploaded` notification fires. Confirm an email from an unknown
  address produces a `drop` log and no document.

## Out of scope for v1 (note in code comments)

- Per-fund or per-investor targeting (org-level only; a `+<org-slug>` tag
  selects the org, but not a fund/investor within it).
- Storing the email body/message itself as a document (attachments only).
- Bounce/forward on failure (explicitly chosen: silent drop + log).
- De-duplication of repeated sends (same file emailed twice ⇒ two documents).
```
