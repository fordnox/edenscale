import PostalMime from "postal-mime";

interface Env {
  /** Backend origin, no trailing slash. e.g. https://api.newtaven.com */
  BACKEND_URL: string;
  /** Shared secret, set via `wrangler secret put EMAIL_INGEST_TOKEN`. */
  EMAIL_INGEST_TOKEN: string;
}

interface IngestAttachment {
  file_name: string;
  mime_type: string;
  content_base64: string;
}

/**
 * Cloudflare Email Routing worker for cc@newtaven.com.
 *
 * Extracts real file attachments from an inbound email and forwards them to the
 * backend's shared-secret ingestion endpoint, which resolves the sender's
 * organization and stores each attachment as a Document.
 *
 * Design decisions (see PLAN.md):
 *  - Routing target is inferred backend-side from the sender's email; this
 *    worker does not parse the recipient for plus-addressing (out of scope v1).
 *  - Unknown/unauthorized senders are DROPPED silently by the backend. This
 *    worker never setReject()s or forward()s — it only logs every outcome so
 *    drops remain traceable in Worker logs (observability is enabled).
 */
export default {
  async email(message, env, ctx): Promise<void> {
    // message.from is the trustworthy SMTP envelope sender (header From: can be
    // spoofed, so we do NOT use parsed.from for authorization).
    const from = message.from;
    const to = message.to;

    // message.raw is a single-use stream — buffer it once before parsing.
    const raw = await new Response(message.raw).arrayBuffer();

    // attachmentEncoding: "base64" makes each attachment.content a base64 string
    // directly, so no manual byte→base64 conversion is needed.
    const parsed = await PostalMime.parse(raw, { attachmentEncoding: "base64" });

    // Keep real file attachments only. Drop inline/related parts (logos,
    // signature images, HTML-embedded CID content) so they don't become docs.
    const attachments: IngestAttachment[] = (parsed.attachments ?? [])
      .filter(
        (a) =>
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

    const payload = {
      sender_email: from,
      subject: parsed.subject ?? "",
      attachments,
    };

    try {
      const res = await fetch(`${env.BACKEND_URL}/email-ingest/documents`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-email-ingest-token": env.EMAIL_INGEST_TOKEN,
        },
        body: JSON.stringify(payload),
      });

      const body = await res.text();
      console.log(
        `[email-ingest] from=${from} to=${to} attachments=${attachments.length} ` +
          `status=${res.status} resp=${body.slice(0, 300)}`,
      );
    } catch (err) {
      // Silent drop per design, but log so failures are visible in Worker logs.
      console.log(
        `[email-ingest] error posting from=${from} to=${to}: ${String(err)}`,
      );
    }
  },
} satisfies ExportedHandler<Env>;
