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
 * Usage:
 *   RESEND_API_KEY=... pnpm push
 *   RESEND_API_KEY=... pnpm push emails/customer/capital_call.tsx
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

type VarType = "string" | "number";

interface TemplateVariableInput {
  key: string;
  type: VarType;
  fallbackValue?: string | number | null;
}

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
  return [...keys].sort().map((key) => {
    const type: VarType = NUMBER_KEYS.has(key) ? "number" : "string";
    return { key, type, fallbackValue: type === "number" ? 0 : "" };
  });
}

async function findExistingId(name: string): Promise<string | null> {
  let after: string | undefined;
  while (true) {
    const res = await resend.templates.list(
      after ? { limit: 100, after } : { limit: 100 },
    );
    if (res.error) {
      console.error("templates.list failed:", res.error);
      return null;
    }
    const data = res.data?.data ?? [];
    const hit = data.find((t) => t.name === name);
    if (hit) return hit.id;
    if (!res.data?.has_more || data.length === 0) return null;
    after = data[data.length - 1].id;
  }
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

  const existingId = await findExistingId(name);
  if (existingId) {
    const res = await resend.templates.remove(existingId);
    if (res.error) {
      console.error(`✗ ${name}: failed to remove existing template:`, res.error.message);
      return;
    }
  }

  const res = await resend.templates.create({ name, html, variables });
  if (res.error || !res.data) {
    console.error(`✗ ${name}:`, res.error?.message);
    return;
  }

  // Templates are created as drafts; publish so they're sendable.
  const pub = await resend.templates.publish(res.data.id);
  if (pub.error) {
    console.error(`✗ ${name}: failed to publish:`, pub.error.message);
    return;
  }

  console.log(
    `✓ ${existingId ? "replaced" : "created"} & published ${name} (${variables.length} vars: ${variables
      .map((v) => v.key)
      .join(", ")})`,
  );
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const files = args.length
    ? args.map((a) => resolve(a))
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
