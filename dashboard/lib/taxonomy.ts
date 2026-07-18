import { readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

import YAML from "yaml";

import { REPO_ROOT } from "@/lib/paths";

export const TAXONOMY_PATH = path.join(REPO_ROOT, "configs", "knowledge_taxonomy.yaml");

/** One classifiable wiki folder: the taxonomy `path` plus its `scope` blurb. */
export type WikiCategoryOption = { path: string; scope: string };

/**
 * Read the classifiable categories from `configs/knowledge_taxonomy.yaml`
 * (the single source of truth shared with the backend classifier). Mirrors
 * the direct-file-read pattern of `lib/goals.ts` / `lib/wiki.ts`. Throws on a
 * malformed taxonomy; callers that must keep rendering (the knowledge page)
 * degrade to auto-classify-only by catching.
 */
export async function listCategories(
  taxonomyPath = TAXONOMY_PATH,
): Promise<WikiCategoryOption[]> {
  const raw = await readFile(taxonomyPath, "utf8");
  const parsed = (YAML.parse(raw) ?? {}) as { categories?: unknown };
  if (!Array.isArray(parsed.categories)) {
    throw new Error(`invalid knowledge taxonomy: ${taxonomyPath} (missing \`categories\`)`);
  }
  return parsed.categories.map((entry, index) => {
    if (entry === null || typeof entry !== "object") {
      throw new Error(`${taxonomyPath}: categories[${index}] must be a mapping`);
    }
    const e = entry as Record<string, unknown>;
    if (typeof e.path !== "string" || e.path.length === 0) {
      throw new Error(`${taxonomyPath}: categories[${index}].path is required`);
    }
    return { path: e.path, scope: typeof e.scope === "string" ? e.scope : "" };
  });
}

/** Valid `default_freshness` tiers (mirrors the `freshness.tiers` keys). */
export const FRESHNESS_TIERS = [
  "permanent",
  "stable",
  "evolving",
  "ephemeral",
] as const;
export type FreshnessTier = (typeof FRESHNESS_TIERS)[number];

/** Atomic write (tmp + rename), mirroring lib/goals.ts::writeGoalsAtomic. */
async function writeTaxonomyAtomic(
  text: string,
  taxonomyPath: string,
): Promise<void> {
  const tmp = `${taxonomyPath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmp, text, "utf8");
  await rename(tmp, taxonomyPath);
}

// We edit the taxonomy as text (whole-line splices), not by reserializing the
// YAML AST: `doc.toString()` re-emits every line and collapses the file's
// hand-aligned inline-comment spacing. Line splicing leaves every untouched
// line byte-identical — surgical, as the file header demands.

/** A `- path:` item start line at the list's 2-space indent. */
const ITEM_START_RE = /^\s*-\s/;
/** Pull the path scalar out of a `- path: <value>` line. */
const ITEM_PATH_RE = /^\s*-\s+path\s*:\s*["']?([^"'\s#]+)/;

/** Locate the `categories:` list: its key line and the exclusive end of its
 *  block (first later line that is neither indented nor blank, else EOF). */
function categoriesBlock(lines: string[]): { keyIdx: number; end: number } {
  const keyIdx = lines.findIndex((l) => /^categories\s*:\s*(#.*)?$/.test(l));
  if (keyIdx === -1) {
    throw new Error("invalid knowledge taxonomy: missing `categories` list");
  }
  let end = lines.length;
  for (let i = keyIdx + 1; i < lines.length; i++) {
    if (lines[i].trim() === "" || /^\s/.test(lines[i])) continue;
    end = i;
    break;
  }
  return { keyIdx, end };
}

/** Line span `[start, end)` and parsed path for each item in the block. */
function itemRanges(
  lines: string[],
  block: { keyIdx: number; end: number },
): { start: number; end: number; path: string | null }[] {
  const starts: number[] = [];
  for (let i = block.keyIdx + 1; i < block.end; i++) {
    if (ITEM_START_RE.test(lines[i])) starts.push(i);
  }
  return starts.map((start, k) => {
    // Exclude trailing blank lines (e.g. the final newline's empty element)
    // so removing the last item doesn't eat them.
    let end = k + 1 < starts.length ? starts[k + 1] : block.end;
    while (end > start + 1 && lines[end - 1].trim() === "") end--;
    return { start, end, path: ITEM_PATH_RE.exec(lines[start])?.[1] ?? null };
  });
}

/** Render a string as a (minimally-quoted) inline YAML scalar. */
function scalar(value: string): string {
  return YAML.stringify(value, { lineWidth: 0 }).trimEnd();
}

/**
 * Append one category to `configs/knowledge_taxonomy.yaml`, inserting it as
 * new lines at the end of the `categories:` list. Throws if the path exists.
 */
export async function addCategory(
  categoryPath: string,
  scope: string,
  defaultFreshness?: FreshnessTier,
  taxonomyPath = TAXONOMY_PATH,
): Promise<void> {
  const lines = (await readFile(taxonomyPath, "utf8")).split("\n");
  const block = categoriesBlock(lines);
  if (itemRanges(lines, block).some((it) => it.path === categoryPath)) {
    throw new Error(`category already exists: ${categoryPath}`);
  }
  const entry = [`  - path: ${categoryPath}`];
  if (scope) entry.push(`    scope: ${scalar(scope)}`);
  if (defaultFreshness) entry.push(`    default_freshness: ${defaultFreshness}`);

  // Insert after the last non-blank line in the block (before any trailing
  // blank lines), so the new entry joins the list cleanly.
  let insertAt = block.end;
  for (let i = block.end - 1; i > block.keyIdx; i--) {
    if (lines[i].trim() !== "") {
      insertAt = i + 1;
      break;
    }
  }
  lines.splice(insertAt, 0, ...entry);
  await writeTaxonomyAtomic(lines.join("\n"), taxonomyPath);
}

/**
 * Remove every category whose `path` equals `folderPath` or sits under it
 * (`folderPath/…`). Returns the number removed (0 for non-taxonomy dirs like
 * `tools`, which is fine — not an error).
 */
export async function removeCategoriesUnder(
  folderPath: string,
  taxonomyPath = TAXONOMY_PATH,
): Promise<number> {
  const lines = (await readFile(taxonomyPath, "utf8")).split("\n");
  const block = categoriesBlock(lines);
  const prefix = `${folderPath}/`;
  const drop = itemRanges(lines, block).filter(
    (it) => it.path === folderPath || (it.path?.startsWith(prefix) ?? false),
  );
  if (drop.length === 0) return 0;
  // Splice bottom-up so earlier indices stay valid.
  for (let i = drop.length - 1; i >= 0; i--) {
    lines.splice(drop[i].start, drop[i].end - drop[i].start);
  }
  await writeTaxonomyAtomic(lines.join("\n"), taxonomyPath);
  return drop.length;
}
