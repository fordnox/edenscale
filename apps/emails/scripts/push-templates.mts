/**
 * Push every TSX template under emails/ to Resend, with the variables list
 * derived from `{{{ key }}}` placeholders in the rendered HTML.
 *
 * Why this exists: react-email's built-in export calls
 * `resend.templates.create({ name, html })` without a `variables` array, which
 * makes the Resend API 422 with
 *   "Variable '<key>' is used in the template but not defined in the variables list".
 * This script does the same upload, but also declares every variable it finds.
 *
 * Templates are matched by name and updated in place (`templates.update`), never
 * removed and recreated — Resend automations reference a template by id, so
 * recreating one detaches it from every automation using it. A new version is
 * published on each push; the id stays stable for the life of the template.
 *
 * Usage:
 *   RESEND_API_KEY=... pnpm push
 *   RESEND_API_KEY=... pnpm push emails/customer/capital_call.tsx
 *   RESEND_API_KEY=... pnpm push emails/customer   (a directory pushes every .tsx under it)
 *
 * Template name on Resend = the file path with separators/non-alphanumerics
 * stripped, e.g. `emails/customer/capital_call.tsx` → `customercapitalcall`.
 * This must match the id derived server-side in
 * backend/app/services/channels/email_channel.py (`re.sub(r"[^a-zA-Z0-9]", "", event_type)`).
 */

import { readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { render } from "@react-email/render";
import { Resend } from "resend";

// Discriminated on `type` so it satisfies both the create and update payloads.
type TemplateVariableInput =
  | { key: string; type: "string"; fallbackValue?: string | null }
  | { key: string; type: "number"; fallbackValue?: number | null };

const EMAILS_ROOT = resolve(import.meta.dirname, "..", "emails");
const PLACEHOLDER_RE = /\{\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}\}/g;

// Keys whose Resend type should be `number`. Every NewTaven payload value is a
// pre-formatted string (amounts via _fmt_money, dates via _fmt_date), so this
// is empty. Add a key here only if a backend payload sends a raw int/float.
const NUMBER_KEYS = new Set<string>([]);

const apiKey = process.env.RESEND_API_KEY;
if (!apiKey) {
  console.error("RESEND_API_KEY is required");
  process.exit(1);
}
const resend = new Resend(apiKey);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (entry.endsWith(".tsx")) out.push(full);
  }
  return out;
}

function templateNameFor(filePath: string): string {
  const rel = relative(EMAILS_ROOT, filePath).replace(/\.tsx$/, "");
  return rel.replace(/[^a-zA-Z0-9]/g, "");
}

function extractVariables(html: string): TemplateVariableInput[] {
  const keys = new Set<string>();
  for (const m of html.matchAll(PLACEHOLDER_RE)) keys.add(m[1]);
  return [...keys].sort().map((key): TemplateVariableInput =>
    NUMBER_KEYS.has(key)
      ? { key, type: "number", fallbackValue: 0 }
      : { key, type: "string", fallbackValue: "" },
  );
}

// name → id for every template on the account, fetched once per run.
let existingIds: Map<string, string> | null = null;

async function loadExistingIds(): Promise<Map<string, string>> {
  if (existingIds) return existingIds;
  const map = new Map<string, string>();
  let after: string | undefined;
  while (true) {
    const res = await resend.templates.list(
      after ? { limit: 100, after } : { limit: 100 },
    );
    if (res.error) throw new Error(`templates.list failed: ${res.error.message}`);
    const data = res.data?.data ?? [];
    for (const t of data) map.set(t.name, t.id);
    if (!res.data?.has_more || data.length === 0) break;
    after = data[data.length - 1].id;
  }
  existingIds = map;
  return map;
}

async function pushOne(filePath: string): Promise<void> {
  const url = pathToFileURL(filePath).href;
  const mod = await import(url);
  const Component = mod.default;
  if (typeof Component !== "function") {
    console.warn(`Skipping ${filePath}: no default export`);
    return;
  }

  const html = await render(Component({}), { pretty: true });
  const variables = extractVariables(html);
  const name = templateNameFor(filePath);

  const ids = await loadExistingIds();
  const existingId = ids.get(name);

  // Update in place rather than remove + create: the template id is what Resend
  // automations reference, so recreating a template silently breaks every
  // automation wired to it.
  let id: string;
  if (existingId) {
    const res = await resend.templates.update(existingId, {
      html,
      variables,
    });
    if (res.error) {
      console.error(`✗ ${name}: failed to update:`, res.error.message);
      return;
    }
    id = existingId;
  } else {
    const res = await resend.templates.create({ name, html, variables });
    if (res.error || !res.data) {
      console.error(`✗ ${name}:`, res.error?.message);
      return;
    }
    id = res.data.id;
    ids.set(name, id);
  }

  // Both create and update leave the change as an unpublished version; publish
  // so it's the one that actually gets sent.
  const pub = await resend.templates.publish(id);
  if (pub.error) {
    console.error(`✗ ${name}: failed to publish:`, pub.error.message);
    return;
  }

  console.log(
    `✓ ${existingId ? "updated" : "created"} & published ${name} (${id}) (${variables.length} vars: ${variables
      .map((v) => v.key)
      .join(", ")})`,
  );
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const files = args.length
    ? args.flatMap((a) => {
        const full = resolve(a);
        return statSync(full).isDirectory()
          ? walk(full).filter((f) => !f.includes("/layout/"))
          : [full];
      })
    : walk(EMAILS_ROOT).filter((f) => !f.includes("/layout/"));

  for (const file of files) {
    try {
      await pushOne(file);
    } catch (err) {
      console.error(`✗ ${file}:`, err);
    }
  }
}

await main();
