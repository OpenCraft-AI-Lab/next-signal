"use server";

import { execFile } from "node:child_process";
import { mkdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { revalidatePath } from "next/cache";

import { spawnPacaDetached } from "@/lib/actions/spawn-paca";
import {
  getDictionary,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/dictionaries";
import { startIngestJob } from "@/lib/ingest/jobs";
import { wikiRoot } from "@/lib/paths";
import {
  addCategory,
  type FreshnessTier,
  FRESHNESS_TIERS,
  removeCategoriesUnder,
} from "@/lib/taxonomy";

const execFileAsync = promisify(execFile);

/** Mirror the backend's resolution (paca.integrations.gbrain): GBRAIN_BIN env
 *  wins, else the `gbrain` launcher on PATH. */
function gbrainBin(): string {
  return process.env.GBRAIN_BIN?.trim() || "gbrain";
}

export type GbrainHit = {
  slug: string;
  score: number;
  snippet: string;
};

/**
 * Parse gbrain's plain-text search output. Each hit looks like:
 *
 *   [0.3789] knowledge-foo-bar -- # Page title
 *
 *   ## Some content
 *   continuing snippet…
 *
 * The next hit starts when we see another `[number]` line prefix.
 */
function parseGbrainOutput(stdout: string): GbrainHit[] {
  const lines = stdout.split("\n");
  const hits: GbrainHit[] = [];
  let current: GbrainHit | null = null;
  const headerRe = /^\[([\d.]+)\]\s+(\S+)\s+--\s?(.*)$/;
  for (const line of lines) {
    const m = headerRe.exec(line);
    if (m) {
      if (current) hits.push(current);
      current = {
        score: Number.parseFloat(m[1]) || 0,
        slug: m[2],
        snippet: m[3] ?? "",
      };
    } else if (current) {
      current.snippet += (current.snippet ? "\n" : "") + line;
    }
  }
  if (current) hits.push(current);
  return hits.map((h) => ({ ...h, snippet: h.snippet.trim() }));
}

export async function searchKnowledge(query: string): Promise<GbrainHit[]> {
  const q = query.trim();
  if (!q) return [];
  try {
    const { stdout } = await execFileAsync(gbrainBin(), [
      "search",
      q,
      "--limit",
      "10",
    ]);
    return parseGbrainOutput(stdout);
  } catch {
    return [];
  }
}

/**
 * Kick off the wiki → GBrain re-ingest. Detached so the toast accurately
 * reflects "started", not "finished". Runs the `knowledge_ingest` workflow's
 * `extra.run_now` entry point (weekly sync: re-embed changed files + refresh
 * Related blocks).
 */
export async function reindexKnowledge(
  localeValue?: Locale,
): Promise<{ ok: boolean; message: string }> {
  const t = getDictionary(normalizeLocale(localeValue));
  const result = await spawnPacaDetached(
    ["run-workflow", "knowledge_ingest"],
    {
      extraEnv: { PACA_WIKI_DIR: wikiRoot() },
      verb: "Re-index",
      logTag: "knowledge-reindex",
    },
  );
  return result.ok ? { ok: true, message: t.actions.reindexStarted } : result;
}

/**
 * Start a tracked knowledge-ingest job from the dashboard form. Returns the
 * job id; live per-step progress is observed via the SSE feed + active-ingests
 * panel, so this returns as soon as the subprocess is spawned. `category` (a
 * taxonomy path) pins the destination folder; empty/undefined = auto-classify.
 */
export async function startKnowledgeIngest(
  value: string,
  category?: string | null,
  localeValue?: Locale,
): Promise<{ ok: boolean; jobId?: string; message: string }> {
  const t = getDictionary(normalizeLocale(localeValue));
  const trimmed = value.trim();
  if (!trimmed) return { ok: false, message: t.knowledge.ingest.errorEmpty };
  const jobId = startIngestJob(trimmed, {
    category: category?.trim() || null,
    source: "knowledge",
  });
  return { ok: true, jobId, message: t.knowledge.ingest.started };
}

/**
 * Resolve a WIKI_ROOT-relative path to an absolute path inside the wiki, or
 * null if it escapes. Same guard as lib/wiki.ts::getWikiDoc: reject absolute
 * paths and any `..` segment, then verify the resolved path stays under root.
 */
function resolveInWiki(rel: string): string | null {
  if (!rel || path.isAbsolute(rel)) return null;
  if (rel.split(/[\\/]/).some((seg) => seg === "..")) return null;
  const root = wikiRoot();
  const abs = path.resolve(root, rel);
  if (abs !== root && !abs.startsWith(root + path.sep)) return null;
  return abs;
}

type ActionResult = { ok: boolean; message: string };

/**
 * Create a wiki folder and register it as a taxonomy category (so it shows in
 * the tree and becomes an ingest destination). Path segments must be safe
 * slug chars; `scope` and `freshness` are optional.
 */
export async function createWikiFolder(
  folderPath: string,
  scope?: string,
  freshness?: string,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue)).knowledge.manage;
  const rel = folderPath
    .trim()
    .replace(/^\/+|\/+$/g, "")
    .replace(/\\/g, "/");
  if (!rel) return { ok: false, message: t.errorPath };
  if (!rel.split("/").every((seg) => /^[a-z0-9][a-z0-9_-]*$/.test(seg))) {
    return { ok: false, message: t.errorPathChars };
  }
  const abs = resolveInWiki(rel);
  if (!abs) return { ok: false, message: t.errorPathChars };

  const tier =
    freshness && FRESHNESS_TIERS.includes(freshness as FreshnessTier)
      ? (freshness as FreshnessTier)
      : undefined;
  try {
    await addCategory(rel, scope?.trim() ?? "", tier);
    await mkdir(abs, { recursive: true });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return {
      ok: false,
      message: msg.includes("already exists") ? t.errorExists : msg,
    };
  }
  revalidatePath("/knowledge");
  return { ok: true, message: t.folderCreated(rel) };
}

/**
 * Delete one wiki markdown doc. For the per-article layout
 * (`<slug>/<slug>.md`) the whole article folder (incl. `images/`) is removed;
 * otherwise just the file. Wiki-file-only: GBrain index / raw archive are left
 * for the next re-index.
 */
export async function deleteWikiDoc(
  id: string,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue)).knowledge.manage;
  if (!id.endsWith(".md")) return { ok: false, message: t.errorNotFound };
  const abs = resolveInWiki(id);
  if (!abs) return { ok: false, message: t.errorNotFound };
  const dir = path.dirname(abs);
  const isArticleDir = path.basename(dir) === path.basename(abs, ".md");
  try {
    await rm(isArticleDir ? dir : abs, { recursive: true, force: false });
  } catch {
    return { ok: false, message: t.errorNotFound };
  }
  revalidatePath("/knowledge");
  return { ok: true, message: t.deleted(path.basename(abs)) };
}

/**
 * Delete a wiki folder (recursively) and prune its taxonomy categories so the
 * ingest dropdown drops the now-gone destination. Refuses the wiki root.
 */
export async function deleteWikiFolder(
  folderPath: string,
  localeValue?: Locale,
): Promise<ActionResult> {
  const t = getDictionary(normalizeLocale(localeValue)).knowledge.manage;
  const rel = folderPath.trim().replace(/^\/+|\/+$/g, "");
  const abs = resolveInWiki(rel);
  if (!rel || !abs || abs === wikiRoot()) {
    return { ok: false, message: t.errorNotFound };
  }
  try {
    if (!(await stat(abs)).isDirectory()) {
      return { ok: false, message: t.errorNotFound };
    }
    await rm(abs, { recursive: true, force: false });
  } catch {
    return { ok: false, message: t.errorNotFound };
  }
  await removeCategoriesUnder(rel);
  revalidatePath("/knowledge");
  return { ok: true, message: t.deleted(path.basename(abs)) };
}
