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
    throw new Error(
      "WIKI_DIR is required; set it in .env and launch via `next-signal dashboard`",
    );
  }
  return dir;
}

/**
 * User-state root, mirroring `next_signal.core.paths.STATE_ROOT` — same env var,
 * same `~/.next-signal` default (unlike `wikiRoot()`, this one always has a
 * sane fallback, so it never throws).
 */
export function stateRoot(): string {
  return (
    process.env.NEXT_SIGNAL_STATE_DIR?.trim() ||
    path.join(os.homedir(), ".next-signal")
  );
}

/**
 * The live content-language preference file both the dashboard and every
 * `next-signal` pipeline container read/write — see `next_signal.core.language`.
 */
export function languageStateFile(): string {
  return path.join(stateRoot(), "language.json");
}

/**
 * The unattended run schedule both the dashboard and the `scheduler` container
 * read/write — see `next_signal.core.schedule`. Absent means never configured,
 * which reads as disabled on both sides.
 */
export function scheduleStateFile(): string {
  return path.join(stateRoot(), "schedule.json");
}

/** Live provider defaults shared with `next_signal.core.coding_agent_preferences`. */
export function codingAgentPreferencesFile(): string {
  return path.join(stateRoot(), "coding-agents.json");
}

/**
 * Which engine next-signal calls, plus the two model-provider sections the
 * coding-agent file does not own — see `lib/engine-preferences.ts`. Written by
 * the settings page and read by `next_signal.agents.stage` at the start of every
 * production job, so an edit here steers the next run. `configs/models.yaml`
 * supplies the baseline profile this file overrides, not the final answer.
 */
export function engineStateFile(): string {
  return path.join(stateRoot(), "engine.json");
}

/**
 * Which embedder the info-radar dedup gate resolves for each item — see
 * `lib/embedding-preferences.ts` and `next_signal.core.embedding_preferences`.
 * Separate from `engine.json` because an embedder has no fallback and no job
 * affinity: switching it parks the dedup memory of the space it left rather
 * than substituting one answer for another.
 *
 * Holds no credential. The generic provider stores the *name* of an
 * environment variable; the value is read from the pipeline process at call
 * time.
 */
export function embeddingStateFile(): string {
  return path.join(stateRoot(), "embedding.json");
}

/**
 * Every provider credential, in one file — see `lib/secrets.ts` and
 * `next_signal.core.secrets`. Written by the settings page and read at call time
 * by every pipeline process, which is what lets a credential saved in the
 * browser reach the running scheduler without recreating it.
 *
 * Unlike every other state file here, this one holds secret values: it is
 * written `0600`, never read back to the browser, and never logged.
 */
export function secretsStateFile(): string {
  return path.join(stateRoot(), "secrets.json");
}
