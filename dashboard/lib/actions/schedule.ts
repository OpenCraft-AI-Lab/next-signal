"use server";

import { readFile } from "node:fs/promises";

import { query } from "@/lib/db";
import { scheduleStateFile } from "@/lib/paths";
import { writeStateFile } from "@/lib/state-file";

/** One scheduled job today: the radar chain. Matches `orchestrator.schedule.JOB`. */
const JOB = "radar";

export interface Schedule {
  enabled: boolean;
  /**
   * Wall-clock "HH:MM" times, sorted and deduplicated; empty when never
   * configured. Every listed time fires every day.
   *
   * The zone they are wall-clock in is `INFO_RADAR_TIMEZONE`, resolved through
   * `next_signal.core.clock` — deliberately not a field here. That one value
   * also fixes radar day grouping and review due dates, so a schedule with a
   * zone of its own could fire at 08:00 in one zone and be filed under a day
   * boundary drawn in another. The settings page states it, read-only.
   */
  at: string[];
  catchUp: boolean;
}

export interface ScheduleStatus {
  /** Start instant while `lastStatus` is `running`, finish instant otherwise. */
  lastRunAt: string | null;
  /**
   * `running` is written before the chain starts, so it is an ordinary value
   * here and not junk to be discarded — a run that takes an hour is otherwise
   * indisplayable. A run the scheduler never finished reads as `failed`.
   */
  lastStatus: "ok" | "failed" | "running" | null;
  lastError: string | null;
}

const STATUSES = ["ok", "failed", "running"] as const;

/** Anything the scheduler did not write reads as no run at all. */
function readStatus(raw: string | null): ScheduleStatus["lastStatus"] {
  return STATUSES.includes(raw as (typeof STATUSES)[number])
    ? (raw as ScheduleStatus["lastStatus"])
    : null;
}

const DISABLED: Schedule = {
  enabled: false,
  at: [],
  catchUp: false,
};

function isValidTime(at: string): boolean {
  return /^([01]\d|2[0-3]):[0-5]\d$/.test(at);
}

/**
 * Normalize `at` to sorted, deduplicated times. Accepts a bare string as well as
 * a list: the field held a single time before multiple daily runs existed, and a
 * file written by that version is still on disk. Mirrors
 * `next_signal.core.schedule._read_times`.
 */
function readTimes(raw: unknown): string[] {
  if (raw == null) return [];
  const values = typeof raw === "string" ? [raw] : raw;
  if (!Array.isArray(values)) throw new Error("`at` must be a string or a list");
  const times = new Set<string>();
  for (const value of values) {
    const text = String(value).trim();
    if (!text) continue;
    if (!isValidTime(text)) throw new Error(`unrecognized time: ${text}`);
    times.add(text);
  }
  return [...times].sort();
}

/**
 * Read the live schedule.
 *
 * Deliberately more forgiving than `next_signal.core.schedule`, which raises on a
 * corrupt file, for the same reason `getContentLanguage` is: the nav renders on
 * every page, so raising here would take down the dashboard — including the
 * panel the operator would use to fix the file. Falls back to disabled and logs.
 */
export async function getSchedule(): Promise<Schedule> {
  let raw: string;
  try {
    raw = await readFile(scheduleStateFile(), "utf-8");
  } catch {
    return DISABLED; // absent is normal (never configured, or fresh volume)
  }
  try {
    const data = JSON.parse(raw);
    return {
      enabled: Boolean(data.enabled),
      at: readTimes(data.at),
      catchUp: Boolean(data.catch_up),
    };
  } catch (err) {
    console.error(`${scheduleStateFile()} is unusable, treating as disabled`, err);
    return DISABLED;
  }
}

/**
 * Write the live schedule, read by the `scheduler` container on its next poll
 * (within 30s — no restart needed). Atomic write (temp file + rename) so a
 * concurrent read never sees a torn file.
 */
export async function setSchedule(next: Schedule): Promise<void> {
  const at = readTimes(next.at); // canonical: validated, deduped, sorted
  if (next.enabled && at.length === 0) {
    throw new Error("an enabled schedule needs at least one time");
  }
  // A `tz` written by an earlier version is dropped here rather than migrated:
  // it never steered a run, so carrying it forward would only preserve the
  // impression that it did. `next_signal.core.schedule` reads named fields with
  // `.get`, so its disappearance is not fatal to an older scheduler either.
  await writeStateFile(
    scheduleStateFile(),
    JSON.stringify({
      enabled: next.enabled,
      at,
      catch_up: next.catchUp,
      updated_at: new Date().toISOString(),
      updated_by: "dashboard",
    }),
  );
}

/**
 * How the last unattended run ended. Tolerates a missing table so a stack that
 * has not been bootstrapped still renders the nav; the panel then reads as
 * never-run, which is what an un-provisioned schedule effectively is.
 */
export async function getScheduleStatus(): Promise<ScheduleStatus> {
  try {
    const rows = await query<{
      last_run_at: Date | null;
      last_status: string | null;
      last_error: string | null;
    }>(
      "SELECT last_run_at, last_status, last_error FROM schedule_state WHERE job = $1",
      [JOB],
    );
    const row = rows[0];
    if (!row) return { lastRunAt: null, lastStatus: null, lastError: null };
    return {
      lastRunAt: row.last_run_at ? row.last_run_at.toISOString() : null,
      lastStatus: readStatus(row.last_status),
      lastError: row.last_error,
    };
  } catch (err) {
    console.error("could not read schedule_state", err);
    return { lastRunAt: null, lastStatus: null, lastError: null };
  }
}
