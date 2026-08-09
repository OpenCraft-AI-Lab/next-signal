import os from "node:os";
import path from "node:path";

/**
 * Absolute path to the `next-signal` repo root.
 * The dashboard lives at `<repo>/dashboard`, so the parent of this file's
 * containing dir is the repo root.
 */
export const REPO_ROOT = path.resolve(process.cwd(), "..");

/**
 * Wiki root from `WIKI_DIR`. Resolved lazily and fails loud when unset —
 * mirrors the backend `next_signal.core.paths`. The env reaches this process when the
 * dashboard is launched via `next-signal dashboard` (which loads `.env`).
 */
export function wikiRoot(): string {
  const dir = process.env.WIKI_DIR?.trim();
  if (!dir) {
    throw new Error("WIKI_DIR is required; set it in .env and launch via `next-signal dashboard`");
  }
  return dir;
}

/**
 * User-state root, mirroring `next_signal.core.paths.STATE_ROOT` — same env var,
 * same `~/.next-signal` default (unlike `wikiRoot()`, this one always has a
 * sane fallback, so it never throws).
 */
export function stateRoot(): string {
  return process.env.NEXT_SIGNAL_STATE_DIR?.trim() || path.join(os.homedir(), ".next-signal");
}

/**
 * The live content-language preference file both the dashboard and every
 * `next-signal` pipeline container read/write — see `next_signal.core.language`.
 */
export function languageStateFile(): string {
  return path.join(stateRoot(), "language.json");
}
