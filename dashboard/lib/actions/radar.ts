"use server";

import {
  execFile,
  spawn,
  type ChildProcess,
} from "node:child_process";
import { mkdir, open } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { query } from "@/lib/db";
import { startIngestJob } from "@/lib/ingest/jobs";
import {
  getDictionary,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/dictionaries";
import { REPO_ROOT } from "@/lib/paths";
import {
  resolveRadarIngestValue,
  type RadarIngestRow,
} from "@/lib/radar-ingest";
import {
  getRunState,
  recordAnalyzeFinish,
  recordAnalyzeStart,
  recordPullClick,
} from "@/lib/radar/run-state";

const execFileAsync = promisify(execFile);

/**
 * Spawn `paca info-radar analyze` TRACKED — non-detached, with the child
 * reference held on `globalThis` so it (and its exit handlers) are not GC'd.
 * The dashboard process stays the parent so the child's exit reliably flips
 * `analyzeRunning` back to false, which the live progress bar polls. stdout/
 * stderr go to the shared dashboard-actions.log; we do NOT parse them —
 * progress is derived from the `radar_analyses` rows the analyzer writes.
 */
async function spawnAnalyzeTracked(): Promise<void> {
  const logPath = path.join(
    os.homedir(),
    ".next-signal",
    "dashboard-actions.log",
  );
  await mkdir(path.dirname(logPath), { recursive: true });
  const handle = await open(logPath, "a");
  await handle.write(
    `[${new Date().toISOString()}] [radar-analyze] spawn: uv run paca info-radar analyze\n`,
  );
  const child = spawn("uv", ["run", "paca", "info-radar", "analyze"], {
    cwd: REPO_ROOT,
    env: { ...process.env },
    stdio: ["ignore", handle.fd, handle.fd],
  });
  // Child inherited the fd; close our own handle.
  await handle.close();

  const g = globalThis as typeof globalThis & {
    pacaRadarAnalyze?: ChildProcess;
  };
  g.pacaRadarAnalyze = child;
  const finish = (): void => {
    if (g.pacaRadarAnalyze === child) g.pacaRadarAnalyze = undefined;
    void recordAnalyzeFinish();
  };
  child.on("close", finish);
  child.on("error", finish);
}

type MaxFetchedRow = { max_fetched: string | null };

function errorMessage(err: unknown): string {
  if (err && typeof err === "object" && "stderr" in err) {
    const stderr = String((err as { stderr?: unknown }).stderr ?? "").trim();
    if (stderr) return stderr.slice(0, 240);
  }
  return err instanceof Error
    ? err.message.slice(0, 240)
    : String(err).slice(0, 240);
}

export async function ingestToWiki(
  itemId: number,
  localeValue?: Locale,
): Promise<{ ok: boolean; message: string }> {
  const t = getDictionary(normalizeLocale(localeValue));
  const rows = await query<RadarIngestRow>(
    "SELECT source, source_id, url, title FROM radar_items WHERE id = $1 LIMIT 1",
    [itemId],
  );
  if (!rows[0]) return { ok: false, message: t.actions.urlMissing };

  let ingestValue: string;
  try {
    ingestValue = await resolveRadarIngestValue(itemId, rows[0]);
  } catch (err) {
    return { ok: false, message: errorMessage(err) };
  }

  // Folo radar rows are resolved to a staged HTML file first because the
  // timeline row only has a short preview. Other sources continue through the
  // normal URL ingest path after URL validation.
  startIngestJob(ingestValue, { source: "radar" });
  return { ok: true, message: t.actions.ingestStarted };
}

export async function runPullAndAnalyze(
  localeValue?: Locale,
): Promise<{ ok: boolean; message: string }> {
  const t = getDictionary(normalizeLocale(localeValue));
  // Snapshot max(fetched_at) BEFORE pull so we can count how many rows
  // pull actually inserted — pull is idempotent via UNIQUE(source,
  // source_id), so a no-op click writes zero rows and max(fetched_at)
  // doesn't move. Recording the click in run-state.json lets the nav
  // chip show "+0 new · 30s ago" instead of staying frozen at the last
  // meaningful pull.
  const before = await query<MaxFetchedRow>(
    "SELECT max(fetched_at)::text AS max_fetched FROM radar_items",
  );
  const beforeMax = before[0]?.max_fetched ?? null;
  const pullStartedAt = new Date().toISOString();

  try {
    await execFileAsync("uv", ["run", "paca", "info-radar", "pull"], {
      cwd: REPO_ROOT,
      maxBuffer: 1024 * 1024,
    });
  } catch (err) {
    return { ok: false, message: errorMessage(err) };
  }

  // Count rows inserted by this pull and record the click.
  const newCountRows = await query<{ n: string }>(
    beforeMax === null
      ? "SELECT count(*)::text AS n FROM radar_items"
      : "SELECT count(*)::text AS n FROM radar_items WHERE fetched_at > $1::timestamptz",
    beforeMax === null ? [] : [beforeMax],
  );
  await recordPullClick(Number(newCountRows[0]?.n ?? 0), pullStartedAt);

  // Already-running guard: a post-reload double click shouldn't stack a second
  // analyze (the in-flight button disable covers the same-tab case). A stray
  // double-run is harmless — mark_seen + UNIQUE(radar_analyses.radar_item_id)
  // dedup it — but skipping keeps the progress bar's denominator coherent.
  if ((await getRunState()).analyzeRunning) {
    return { ok: true, message: t.actions.analyzeAlreadyRunning };
  }

  // Progress denominator: how many unseen items the analyzer will work
  // through. Captured AFTER pull because pull may have just added unseen rows.
  const unseen = await query<{ n: string }>(
    "SELECT count(*)::text AS n FROM radar_items WHERE seen_at IS NULL",
  );
  const total = Number(unseen[0]?.n ?? 0);

  await recordAnalyzeStart(total);
  try {
    await spawnAnalyzeTracked();
  } catch (err) {
    // Spawn failed synchronously (missing uv, EACCES) — undo the running marker.
    await recordAnalyzeFinish();
    return { ok: false, message: errorMessage(err) };
  }
  return { ok: true, message: t.actions.pullCompleteAnalyzeStarted };
}
