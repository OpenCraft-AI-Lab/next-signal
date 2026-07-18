import { query } from "@/lib/db";
import { getRunState } from "@/lib/radar/run-state";

// Live run-state read — never cache.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Poll endpoint for the live analyze-progress bar. Returns the current run
 * state of a dashboard-triggered analyze:
 *   - `running` — the `analyzeRunning` marker from radar-state.json (the
 *     authoritative "is a run in flight" signal; never inferred from done/total).
 *   - `done`    — items processed so far = radar_analyses rows written since the
 *     latest analyze start (the same query the analyze nav chip uses).
 *   - `total`   — unseen-item count captured at analyze start (the denominator).
 */
export async function GET(): Promise<Response> {
  const state = await getRunState();
  if (!state.lastAnalyzeAt) {
    return Response.json({ running: false, done: 0, total: 0 });
  }
  const rows = await query<{ n: string }>(
    "SELECT count(*)::text AS n FROM radar_analyses WHERE analyzed_at >= $1::timestamptz",
    [state.lastAnalyzeAt],
  );
  return Response.json({
    running: state.analyzeRunning,
    done: Number(rows[0]?.n ?? 0),
    total: state.analyzeTotal,
  });
}
