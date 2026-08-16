import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { secretsStateFile } from "@/lib/paths";
import { CREDENTIAL_NAMES, parseSecrets } from "@/lib/secrets";

const execFileAsync = promisify(execFile);
const DEFAULT_FOLO_ARGV = ["npx", "--yes", "folocli@0.0.5"];

export type RadarIngestRow = {
  source: string | null;
  source_id: string | null;
  url: string | null;
  title: string | null;
};

export type FoloEntry = {
  content?: unknown;
  title?: unknown;
  url?: unknown;
  author?: unknown;
  publishedAt?: unknown;
};

type Deps = {
  fetchFoloEntry: (sourceId: string) => Promise<FoloEntry>;
  stageFoloEntry: (
    itemId: number,
    row: RadarIngestRow,
    entry: FoloEntry,
  ) => Promise<string>;
};

const defaultDeps: Deps = {
  fetchFoloEntry,
  stageFoloEntry,
};

export async function resolveRadarIngestValue(
  itemId: number,
  row: RadarIngestRow,
  deps: Deps = defaultDeps,
): Promise<string> {
  const source = row.source ?? "";
  if (source.startsWith("folo")) {
    const sourceId = row.source_id?.trim();
    if (!sourceId) throw new Error(`radar item ${itemId} has no source_id`);
    const entry = await deps.fetchFoloEntry(sourceId);
    const content = stringField(entry.content).trim();
    if (!content) {
      throw new Error(
        `folocli entry get returned no content for radar item ${itemId}`,
      );
    }
    return deps.stageFoloEntry(itemId, row, entry);
  }

  const url = row.url?.trim();
  if (!url) throw new Error("radar item URL is missing");
  try {
    new URL(url);
  } catch {
    throw new Error("radar item URL is malformed");
  }
  return url;
}

export async function fetchFoloEntry(sourceId: string): Promise<FoloEntry> {
  const argv = foloArgv();
  const env = await folocliEnv();
  let stdout: string;
  try {
    const result = await execFileAsync(
      argv[0],
      [...argv.slice(1), "entry", "get", sourceId],
      {
        env,
        maxBuffer: 10 * 1024 * 1024,
        timeout: 60_000,
      },
    );
    stdout = result.stdout;
  } catch (err) {
    const maybeStdout = (err as { stdout?: unknown }).stdout;
    if (!maybeStdout) throw new Error(errorMessage(err));
    stdout = String(maybeStdout);
  }
  return parseFoloEntryEnvelope(stdout);
}

export function parseFoloEntryEnvelope(stdout: string): FoloEntry {
  let envelope: unknown;
  try {
    envelope = JSON.parse(stdout);
  } catch (err) {
    throw new Error(`folocli entry get non-JSON output: ${String(err)}`);
  }
  if (!envelope || typeof envelope !== "object" || !("ok" in envelope)) {
    throw new Error("folocli entry get: missing ok envelope field");
  }
  const obj = envelope as { ok?: unknown; data?: unknown; error?: unknown };
  if (!obj.ok) {
    const err = obj.error && typeof obj.error === "object" ? obj.error : {};
    const code = "code" in err ? String(err.code) : "UNKNOWN";
    const message = "message" in err ? String(err.message) : "no message";
    throw new Error(`folocli entry get ok=false: ${code}: ${message}`);
  }
  const data = obj.data && typeof obj.data === "object" ? obj.data : {};
  const entries = "entries" in data ? data.entries : null;
  if (!entries || typeof entries !== "object") {
    throw new Error("folocli entry get: data.entries missing or not an object");
  }
  return entries as FoloEntry;
}

export async function stageFoloEntry(
  itemId: number,
  row: RadarIngestRow,
  entry: FoloEntry,
): Promise<string> {
  const dir = path.join(agentTmpDir(), "radar-ingest");
  await mkdir(dir, { recursive: true });
  const filePath = path.join(dir, `radar-${itemId}-${randomUUID()}.html`);
  await writeFile(filePath, renderFoloEntryHtml(row, entry), "utf8");
  return filePath;
}

export function renderFoloEntryHtml(
  row: RadarIngestRow,
  entry: FoloEntry,
): string {
  const title = stringField(entry.title) || row.title || `Radar item`;
  const sourceUrl = stringField(entry.url) || row.url || "";
  const author = stringField(entry.author);
  const publishedAt = stringField(entry.publishedAt);
  const content = stringField(entry.content);
  const metadata = [
    sourceUrl
      ? `<p><strong>Source:</strong> <a href="${escapeAttr(sourceUrl)}">${escapeHtml(sourceUrl)}</a></p>`
      : "",
    author ? `<p><strong>Author:</strong> ${escapeHtml(author)}</p>` : "",
    publishedAt
      ? `<p><strong>Published:</strong> ${escapeHtml(publishedAt)}</p>`
      : "",
  ]
    .filter(Boolean)
    .join("\n");
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(title)}</title>
  ${sourceUrl ? `<link rel="canonical" href="${escapeAttr(sourceUrl)}">` : ""}
</head>
<body>
  <article>
    <h1>${escapeHtml(title)}</h1>
    ${metadata}
    ${content}
  </article>
</body>
</html>
`;
}

/**
 * Env for the one folocli child this module spawns. Mirrors
 * `next_signal.core.secrets.child_env`: read the credential store fresh at
 * spawn time (not `process.env`, which never holds it — nothing writes
 * FOLO_TOKEN there), strip every known credential name from the inherited
 * environment first, then put back only FOLO_TOKEN. Duplicated here rather
 * than reused from `lib/actions/secrets.ts` because that module is `"use
 * server"` and deliberately exports no function that returns a credential
 * value — doing so here, in a plain (non-action) module, keeps that
 * boundary intact.
 */
export async function folocliEnv(): Promise<NodeJS.ProcessEnv> {
  let raw: string;
  try {
    raw = await readFile(secretsStateFile(), "utf-8");
  } catch {
    raw = "{}"; // absent store is normal — a fresh install has no credentials
  }
  const secrets = parseSecrets(raw);
  const token = secrets.FOLO_TOKEN?.trim();
  if (!token) {
    throw new Error(
      "FOLO_TOKEN is not configured. Set it on the dashboard settings page (Settings -> Credentials).",
    );
  }
  const env = { ...process.env };
  for (const name of CREDENTIAL_NAMES) delete env[name];
  env.FOLO_TOKEN = token;
  return env;
}

function foloArgv(): string[] {
  const override = process.env.FOLO_CLI_ARGV?.trim();
  return override
    ? override.split(/\s+/).filter(Boolean)
    : [...DEFAULT_FOLO_ARGV];
}

function agentTmpDir(): string {
  if (process.env.NEXT_SIGNAL_AGENT_TMP_DIR?.trim())
    return process.env.NEXT_SIGNAL_AGENT_TMP_DIR.trim();
  const stateRoot =
    process.env.NEXT_SIGNAL_STATE_DIR?.trim() ||
    path.join(os.homedir(), ".next-signal");
  return path.join(stateRoot, "agent-tmp");
}

function stringField(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttr(value: string): string {
  return escapeHtml(value).replace(/"/g, "&quot;");
}

function errorMessage(err: unknown): string {
  if (err && typeof err === "object" && "stderr" in err) {
    const stderr = String((err as { stderr?: unknown }).stderr ?? "").trim();
    if (stderr) return stderr.slice(0, 240);
  }
  return err instanceof Error
    ? err.message.slice(0, 240)
    : String(err).slice(0, 240);
}
