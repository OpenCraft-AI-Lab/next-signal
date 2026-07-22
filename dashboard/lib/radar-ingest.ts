import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

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
  let stdout: string;
  try {
    const result = await execFileAsync(
      argv[0],
      [...argv.slice(1), "entry", "get", sourceId],
      {
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
  // Provenance goes in a sibling `.meta.json` sidecar (structured data the
  // pipeline reads into frontmatter), NOT as an English label block in the body.
  await writeFile(
    filePath.replace(/\.html$/, ".meta.json"),
    JSON.stringify(foloEntryMetadata(row, entry)),
    "utf8",
  );
  return filePath;
}

export function foloEntryMetadata(
  row: RadarIngestRow,
  entry: FoloEntry,
): Record<string, string> {
  const sourceUrl = stringField(entry.url) || row.url || "";
  const author = stringField(entry.author);
  const publishedAt = stringField(entry.publishedAt);
  const meta: Record<string, string> = {};
  if (sourceUrl) meta.source_url = sourceUrl;
  if (author) meta.author = author;
  if (publishedAt) meta.published = publishedAt;
  return meta;
}

export function renderFoloEntryHtml(
  row: RadarIngestRow,
  entry: FoloEntry,
): string {
  const title = stringField(entry.title) || row.title || `Radar item`;
  const sourceUrl = stringField(entry.url) || row.url || "";
  const content = stringField(entry.content);
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
    ${content}
  </article>
</body>
</html>
`;
}

function foloArgv(): string[] {
  const override = process.env.FOLO_CLI_ARGV?.trim();
  return override
    ? override.split(/\s+/).filter(Boolean)
    : [...DEFAULT_FOLO_ARGV];
}

function agentTmpDir(): string {
  if (process.env.PACA_AGENT_TMP_DIR?.trim())
    return process.env.PACA_AGENT_TMP_DIR.trim();
  const stateRoot =
    process.env.PACA_STATE_DIR?.trim() ||
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
