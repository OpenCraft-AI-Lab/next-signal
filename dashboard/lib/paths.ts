import path from "node:path";

/**
 * Absolute path to the `next-signal` repo root.
 * The dashboard lives at `<repo>/dashboard`, so the parent of this file's
 * containing dir is the repo root.
 */
export const REPO_ROOT = path.resolve(process.cwd(), "..");

/**
 * Wiki root from `PACA_WIKI_DIR`. Resolved lazily and fails loud when unset —
 * mirrors the backend `paca.core.paths`. The env reaches this process when the
 * dashboard is launched via `paca dashboard` (which loads `.env`).
 */
export function wikiRoot(): string {
  const dir = process.env.PACA_WIKI_DIR?.trim();
  if (!dir) {
    throw new Error("PACA_WIKI_DIR is required; set it in .env and launch via `paca dashboard`");
  }
  return dir;
}
