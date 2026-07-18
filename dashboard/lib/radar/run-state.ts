import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

/**
 * Tiny state file that records the most recent Pull+Analyze click so the
 * nav chips can show "+0 new items · 30s ago" instead of "+N · whenever
 * the last meaningful pull was".
 *
 * Two MAX(*) queries can't see a 0-result run because no rows are
 * written; this file IS the source of truth for "when did the operator
 * last click". It lives alongside `dashboard-actions.log` so all
 * dashboard runtime state is in one directory.
 *
 * Writes go through `recordPullClick` / `recordAnalyzeStart` /
 * `recordAnalyzeFinish`; the file is JSON, overwritten atomically each time.
 */
const STATE_PATH = path.join(
  os.homedir(),
  ".intelligent-digitalpaca",
  "radar-state.json",
);

export type RadarRunState = {
  /** ISO timestamp captured immediately before the most recent pull starts. */
  lastPullStartAt: string | null;
  /** ISO timestamp of the most recent pull-phase completion (success). */
  lastPullAt: string | null;
  /** Number of NEW radar_items inserted by that pull (0 is meaningful). */
  lastPullNew: number;
  /** ISO timestamp of the most recent analyze-phase spawn. */
  lastAnalyzeAt: string | null;
  /** True between an analyze spawn and its child's exit. Drives the live
   *  progress bar; authoritative "is a run in flight" signal (never inferred
   *  from done/total — tier1-error items never produce an analysis row). */
  analyzeRunning: boolean;
  /** Unseen radar_items count captured at the most recent analyze start — the
   *  progress bar's denominator. */
  analyzeTotal: number;
};

const EMPTY: RadarRunState = {
  lastPullStartAt: null,
  lastPullAt: null,
  lastPullNew: 0,
  lastAnalyzeAt: null,
  analyzeRunning: false,
  analyzeTotal: 0,
};

async function readState(): Promise<RadarRunState> {
  try {
    const raw = await readFile(STATE_PATH, "utf8");
    const parsed = JSON.parse(raw) as Partial<RadarRunState>;
    return {
      lastPullStartAt: parsed.lastPullStartAt ?? null,
      lastPullAt: parsed.lastPullAt ?? null,
      lastPullNew: typeof parsed.lastPullNew === "number" ? parsed.lastPullNew : 0,
      lastAnalyzeAt: parsed.lastAnalyzeAt ?? null,
      analyzeRunning: parsed.analyzeRunning === true,
      analyzeTotal:
        typeof parsed.analyzeTotal === "number" ? parsed.analyzeTotal : 0,
    };
  } catch {
    return { ...EMPTY };
  }
}

async function writeState(state: RadarRunState): Promise<void> {
  await mkdir(path.dirname(STATE_PATH), { recursive: true });
  const tmp = `${STATE_PATH}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmp, JSON.stringify(state, null, 2) + "\n", "utf8");
  await rename(tmp, STATE_PATH);
}

/** Record a successful pull completion with the count of new items inserted. */
export async function recordPullClick(
  newItems: number,
  startedAt: string = new Date().toISOString(),
): Promise<void> {
  const state = await readState();
  state.lastPullStartAt = startedAt;
  state.lastPullAt = new Date().toISOString();
  state.lastPullNew = newItems;
  await writeState(state);
}

/** Record an analyze-phase start: when we kicked it off, how many unseen items
 *  it will work through (the progress denominator), and that a run is now in
 *  flight. Completion is recorded separately by `recordAnalyzeFinish`. */
export async function recordAnalyzeStart(total: number): Promise<void> {
  const state = await readState();
  state.lastAnalyzeAt = new Date().toISOString();
  state.analyzeTotal = total;
  state.analyzeRunning = true;
  await writeState(state);
}

/** Mark the in-flight analyze run finished (child exited). Leaves
 *  `lastAnalyzeAt` / `analyzeTotal` intact so the nav chip and a final
 *  progress read stay meaningful. */
export async function recordAnalyzeFinish(): Promise<void> {
  const state = await readState();
  state.analyzeRunning = false;
  await writeState(state);
}

/** Read the latest run state. Safe to call from server components — no
 *  exception is thrown if the file is missing or malformed. */
export async function getRunState(): Promise<RadarRunState> {
  return readState();
}
