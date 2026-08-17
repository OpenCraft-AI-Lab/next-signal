"use server";

import { execFile, spawn } from "node:child_process";
import { mkdir, open } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { promisify } from "node:util";

import { REPO_ROOT } from "@/lib/paths";

const execFileAsync = promisify(execFile);

/**
 * Shared launcher for any dashboard server action that needs to run a
 * `uv run next-signal ...` subprocess detached.
 *
 * Contract:
 * - Always cwd at REPO_ROOT.
 * - Always detached + stdio piped to a daily log file under
 *   ~/.next-signal/dashboard-actions.log so the operator can
 *   `tail -f` to debug what the dashboard kicked off.
 * - Returns immediately. Result message is always "<verb> started" on
 *   success — NEVER "completed", because the subprocess outlives this
 *   call and we have no idea if it succeeded.
 * - On synchronous spawn failure (missing `uv` on PATH, EACCES, etc.),
 *   returns `{ok: false}` with the OS error message.
 */
export async function spawnCliDetached(
  argv: string[],
  opts?: {
    /** Extra env vars layered on top of process.env. */
    extraEnv?: Record<string, string>;
    /** Short verb shown in the success toast, e.g. "Pull" → "Pull started". */
    verb?: string;
    /** Tag prefix added to each log line so callers can grep their output. */
    logTag?: string;
  },
): Promise<{ ok: boolean; message: string }> {
  const verb = opts?.verb ?? argv.slice(0, 3).join(" ");
  const logTag = opts?.logTag ?? argv[0] ?? "next-signal";
  const logPath = path.join(os.homedir(), ".next-signal", "dashboard-actions.log");
  await mkdir(path.dirname(logPath), { recursive: true });
  const handle = await open(logPath, "a");
  const ts = new Date().toISOString();
  await handle.write(`[${ts}] [${logTag}] spawn: uv run next-signal ${argv.join(" ")}\n`);

  try {
    const child = spawn("uv", ["run", "next-signal", ...argv], {
      cwd: REPO_ROOT,
      env: { ...process.env, ...opts?.extraEnv },
      detached: true,
      stdio: ["ignore", handle.fd, handle.fd],
    });
    // Once stdio inherits the fd, we can close our own handle.
    await handle.close();
    child.unref();
    return { ok: true, message: `${verb} started` };
  } catch (err) {
    await handle.close().catch(() => {});
    const msg = err instanceof Error ? err.message : String(err);
    return { ok: false, message: msg.slice(0, 200) };
  }
}

/**
 * Run a `uv run next-signal ...` subprocess to completion and return its
 * result. The counterpart to `spawnCliDetached` for the one caller (GBrain
 * initialization) that needs to know the outcome before it can decide
 * whether to lock its section — "started" semantics are wrong here, since
 * this action's whole job is to report what actually happened.
 *
 * Bounded at 310s: `gbrain-init`'s own subprocess call already times out at
 * 300s server-side, and this just needs to outlast that by a margin, not
 * define a new limit.
 */
export async function runCliAwaited(
  argv: string[],
): Promise<{ ok: boolean; stdout: string; stderr: string }> {
  try {
    const { stdout, stderr } = await execFileAsync("uv", ["run", "next-signal", ...argv], {
      cwd: REPO_ROOT,
      env: process.env,
      timeout: 310_000,
      maxBuffer: 10 * 1024 * 1024,
    });
    return { ok: true, stdout, stderr };
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; message?: string };
    return {
      ok: false,
      stdout: e.stdout ?? "",
      stderr: e.stderr || e.message || String(err),
    };
  }
}
