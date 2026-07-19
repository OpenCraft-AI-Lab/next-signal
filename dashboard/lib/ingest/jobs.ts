import "server-only";

import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { EventEmitter } from "node:events";
import { appendFile, mkdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { REPO_ROOT } from "@/lib/paths";
import {
  INGEST_STEPS,
  type IngestJob,
  type IngestSource,
  type IngestStep,
  type StepStatus,
} from "@/lib/ingest/types";

export type { IngestJob, IngestSource, IngestStep, StepStatus } from "@/lib/ingest/types";
export { INGEST_STEPS } from "@/lib/ingest/types";

/**
 * Shared in-process ingest-job registry. Both the /knowledge form and the
 * /radar "Ingest to wiki" action create a job here via `startIngestJob`, so
 * the /knowledge active-ingests panel can show live per-step progress for
 * every ingest regardless of where it was triggered.
 *
 * In-memory by design (single local Node process): progress views for
 * in-flight jobs are lost on a dashboard restart, though the spawned ingest
 * subprocess and its artifact write are unaffected.
 */

const MAX_FINISHED = 20;
const FINISHED_TTL_MS = 5 * 60_000;
const LOG_PATH = path.join(os.homedir(), ".next-signal", "dashboard-actions.log");

type Registry = { jobs: Map<string, IngestJob>; emitter: EventEmitter };

function registry(): Registry {
  const g = globalThis as typeof globalThis & { pacaIngestJobs?: Registry };
  if (!g.pacaIngestJobs) {
    const emitter = new EventEmitter();
    emitter.setMaxListeners(0); // one listener per open SSE connection
    g.pacaIngestJobs = { jobs: new Map(), emitter };
  }
  return g.pacaIngestJobs;
}

export function ingestEmitter(): EventEmitter {
  return registry().emitter;
}

export function listJobs(): IngestJob[] {
  return [...registry().jobs.values()].sort((a, b) =>
    a.startedAt.localeCompare(b.startedAt),
  );
}

function emit(job: IngestJob): void {
  registry().emitter.emit("update", job);
}

async function logLine(line: string): Promise<void> {
  try {
    await mkdir(path.dirname(LOG_PATH), { recursive: true });
    await appendFile(LOG_PATH, line.endsWith("\n") ? line : `${line}\n`);
  } catch {
    // logging is best-effort; never break ingest because the log is unwritable
  }
}

function pruneFinished(): void {
  const { jobs } = registry();
  const finished = [...jobs.values()].filter((j) => j.status !== "running");
  if (finished.length <= MAX_FINISHED) return;
  finished
    .sort((a, b) => (a.finishedAt ?? "").localeCompare(b.finishedAt ?? ""))
    .slice(0, finished.length - MAX_FINISHED)
    .forEach((j) => jobs.delete(j.id));
}

/** Start a tracked ingest; returns the job id immediately (subprocess runs on). */
export function startIngestJob(
  value: string,
  opts: { category?: string | null; source: IngestSource },
): string {
  const { jobs, emitter } = registry();
  const id = randomUUID();
  const job: IngestJob = {
    id,
    value,
    category: opts.category ?? null,
    source: opts.source,
    status: "running",
    steps: Object.fromEntries(INGEST_STEPS.map((s) => [s, "pending"])) as Record<
      IngestStep,
      StepStatus
    >,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    result: null,
    error: null,
  };
  jobs.set(id, job);
  emit(job);

  const argv = ["run", "paca", "knowledge", "ingest", value];
  if (opts.category) argv.push("--category", opts.category);
  argv.push("--progress");
  void logLine(`[${job.startedAt}] [ingest:${opts.source}:${id}] spawn: uv ${argv.join(" ")}`);

  const child = spawn("uv", argv, {
    cwd: REPO_ROOT,
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
  });

  let buffer = "";
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    buffer += chunk;
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) handleLine(job, line);
    }
  });

  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk: string) => {
    void logLine(`[ingest:${opts.source}:${id}] ${chunk.trimEnd()}`);
  });

  const finalize = (status: "done" | "error", error?: string): void => {
    if (job.status !== "running") return;
    job.status = status;
    job.finishedAt = new Date().toISOString();
    if (error) job.error = error;
    if (status === "error") {
      for (const s of INGEST_STEPS) {
        if (job.steps[s] === "running" || job.steps[s] === "pending") job.steps[s] = "error";
      }
    }
    emit(job);
    pruneFinished();
    setTimeout(() => {
      jobs.delete(id);
      emitter.emit("remove", id);
    }, FINISHED_TTL_MS).unref?.();
  };

  child.on("error", (err) => finalize("error", err.message));
  child.on("close", (code) => {
    if (code === 0 && job.result?.ok === true) {
      finalize("done");
    } else {
      const resultError =
        typeof job.result?.error === "string" ? (job.result.error as string) : null;
      finalize("error", job.error ?? resultError ?? `ingest exited with code ${code}`);
    }
  });

  return id;
}

/** Parse one stdout line; skip anything that isn't a known event/result shape. */
function handleLine(job: IngestJob, line: string): void {
  let obj: Record<string, unknown>;
  try {
    const parsed = JSON.parse(line);
    if (parsed === null || typeof parsed !== "object") return;
    obj = parsed as Record<string, unknown>;
  } catch {
    return; // stray non-JSON (e.g. a log line) — ignore
  }

  // Progress event: {"step": <name>, "status": "start"|"done"|"error"}
  if (typeof obj.step === "string" && typeof obj.status === "string") {
    const step = obj.step as IngestStep;
    if (!(INGEST_STEPS as readonly string[]).includes(step)) return;
    const mapped: StepStatus | null =
      obj.status === "start"
        ? "running"
        : obj.status === "done"
          ? "done"
          : obj.status === "error"
            ? "error"
            : null;
    if (!mapped) return;
    job.steps[step] = mapped;
    if (mapped === "error" && typeof obj.error === "string") job.error = obj.error;
    emit(job);
    return;
  }

  // Final result line: {"ok": bool, "source_type"/"markdown_path"/"category", ...}
  if (
    typeof obj.ok === "boolean" &&
    ("markdown_path" in obj || "source_type" in obj || "category" in obj)
  ) {
    job.result = obj;
    if (obj.ok === false && typeof obj.error === "string") job.error = obj.error;
    emit(job);
  }
}
