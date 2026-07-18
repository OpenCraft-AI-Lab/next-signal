import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { REPO_ROOT } from "@/lib/paths";

const execFileAsync = promisify(execFile);

export type SubscriptionRow = {
  id: string;
  title: string;
  feedUrl: string;
  siteUrl: string | null;
  category: string;
  unread: number | null;
  updatedAt: string | null;
};

export type SubscriptionsState =
  | { ok: true; rows: SubscriptionRow[] }
  | { ok: false; message: string };

function errorMessage(err: unknown): string {
  if (err && typeof err === "object" && "stderr" in err) {
    const stderr = String((err as { stderr?: unknown }).stderr ?? "").trim();
    if (stderr) return stderr.slice(0, 400);
  }
  if (err && typeof err === "object" && "stdout" in err) {
    const stdout = String((err as { stdout?: unknown }).stdout ?? "").trim();
    if (stdout) return stdout.slice(0, 400);
  }
  return err instanceof Error ? err.message.slice(0, 400) : String(err).slice(0, 400);
}

function normalizeRows(value: unknown): SubscriptionRow[] {
  if (!Array.isArray(value)) throw new Error("subscription command returned non-list JSON");
  return value.map((row, index) => {
    if (row === null || typeof row !== "object" || Array.isArray(row)) {
      throw new Error(`subscription row ${index} is not an object`);
    }
    const raw = row as Record<string, unknown>;
    return {
      id: String(raw.id ?? raw.feedUrl ?? raw.title ?? index),
      title: typeof raw.title === "string" && raw.title ? raw.title : "(untitled)",
      feedUrl: typeof raw.feedUrl === "string" ? raw.feedUrl : "",
      siteUrl: typeof raw.siteUrl === "string" ? raw.siteUrl : null,
      category:
        typeof raw.category === "string" && raw.category ? raw.category : "Uncategorized",
      unread: typeof raw.unread === "number" && Number.isFinite(raw.unread) ? raw.unread : null,
      updatedAt: typeof raw.updatedAt === "string" ? raw.updatedAt : null,
    };
  });
}

export async function getSubscriptions(): Promise<SubscriptionsState> {
  try {
    const result = await execFileAsync("uv", ["run", "paca", "info-radar", "subscriptions", "--json"], {
      cwd: REPO_ROOT,
      maxBuffer: 1024 * 1024,
      timeout: 90_000,
    });
    return { ok: true, rows: normalizeRows(JSON.parse(result.stdout)) };
  } catch (error) {
    return { ok: false, message: errorMessage(error) };
  }
}
