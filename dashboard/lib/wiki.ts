import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";

import matter from "gray-matter";

import { wikiRoot } from "@/lib/paths";

export type WikiDocSummary = {
  /** Stable id = path relative to WIKI_ROOT, no leading slash. */
  id: string;
  title: string;
  /** ISO-ish date string (frontmatter `captured_at` / `updated_at` or mtime). */
  updated: string;
  tags: string[];
};

/**
 * One node in the wiki tree. A `folder` mirrors a real wiki directory (its
 * `path` is the WIKI_ROOT-relative path, i.e. the taxonomy path); a `doc` is a
 * single markdown artifact. Empty folders are kept so freshly-created folders
 * show up before anything is ingested into them.
 */
export type WikiNode =
  | {
      kind: "folder";
      /** Directory basename, for display. */
      name: string;
      /** WIKI_ROOT-relative path (taxonomy path). */
      path: string;
      /** Total docs in the subtree (badge count). */
      docCount: number;
      children: WikiNode[];
    }
  | { kind: "doc"; doc: WikiDocSummary };

export type WikiDoc = WikiDocSummary & {
  body: string;
  frontmatter: Record<string, unknown>;
};

const EXCLUDED_DIRS = new Set([".git", ".obsidian", "output", "node_modules"]);

/**
 * Is `dir` a self-contained per-article folder (`<slug>/<slug>.md`, possibly
 * with a sibling `images/`)? Such folders render as a single doc leaf, not a
 * folder we descend into — mirrors the persist-stage layout.
 */
async function perArticleDoc(dir: string): Promise<string | null> {
  const md = path.join(dir, `${path.basename(dir)}.md`);
  try {
    if ((await stat(md)).isFile()) return md;
  } catch {
    // no matching .md — not a per-article folder
  }
  return null;
}

async function summarize(file: string): Promise<WikiDocSummary> {
  const raw = await readFile(file, "utf8");
  const { data } = matter(raw);
  const updated =
    typeof data.captured_at === "string"
      ? data.captured_at
      : typeof data.updated_at === "string"
        ? data.updated_at
        : typeof data.created_at === "string"
          ? data.created_at
          : (await stat(file)).mtime.toISOString();
  const title =
    typeof data.title === "string"
      ? data.title
      : path.basename(file, ".md");
  const tags = Array.isArray(data.tags)
    ? (data.tags as unknown[]).filter((t): t is string => typeof t === "string")
    : [];
  return {
    id: path.relative(wikiRoot(), file),
    title,
    updated: updated.slice(0, 10),
    tags,
  };
}

function countDocs(nodes: WikiNode[]): number {
  return nodes.reduce(
    (sum, n) => sum + (n.kind === "doc" ? 1 : n.docCount),
    0,
  );
}

/** Build the child nodes of one wiki directory. Folders are kept even when
 *  empty so newly-created folders are visible before anything lands in them. */
async function buildChildren(dir: string): Promise<WikiNode[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const folders: Extract<WikiNode, { kind: "folder" }>[] = [];
  const docs: Extract<WikiNode, { kind: "doc" }>[] = [];
  for (const entry of entries) {
    if (EXCLUDED_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      const articleMd = await perArticleDoc(full);
      if (articleMd) {
        docs.push({ kind: "doc", doc: await summarize(articleMd) });
        continue;
      }
      const children = await buildChildren(full);
      folders.push({
        kind: "folder",
        name: entry.name,
        path: path.relative(wikiRoot(), full),
        docCount: countDocs(children),
        children,
      });
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      docs.push({ kind: "doc", doc: await summarize(full) });
    }
  }
  folders.sort((a, b) => a.path.localeCompare(b.path));
  docs.sort((a, b) => b.doc.updated.localeCompare(a.doc.updated));
  return [...folders, ...docs];
}

/**
 * Walk WIKI_ROOT and return the wiki tree as nested folder/doc nodes. Folders
 * mirror real directories (including empty ones); per-article folders collapse
 * into a single doc leaf.
 */
export async function listWikiTree(): Promise<WikiNode[]> {
  try {
    return await buildChildren(wikiRoot());
  } catch {
    return [];
  }
}

export async function getWikiDoc(id: string): Promise<WikiDoc | null> {
  // Restrict to wiki markdown files only — we render the body as text so any
  // non-`.md` file we serve here would still be exposed verbatim. Reject
  // absolute paths and any `..` segment up front; then verify the resolved
  // path stays inside WIKI_ROOT. Defense in depth: the second check catches
  // edge cases the first one misses (e.g. symlinks, normalized paths).
  if (!id.endsWith(".md")) return null;
  if (path.isAbsolute(id)) return null;
  if (id.split(/[\\/]/).some((seg) => seg === "..")) return null;
  const root = wikiRoot();
  const abs = path.resolve(root, id);
  if (!abs.startsWith(root + path.sep)) return null;
  try {
    const raw = await readFile(abs, "utf8");
    const { data, content } = matter(raw);
    const summary = await summarize(abs);
    return {
      ...summary,
      body: content,
      frontmatter: data,
    };
  } catch {
    return null;
  }
}
