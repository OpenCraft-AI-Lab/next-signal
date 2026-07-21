import { query } from "@/lib/db";
import { RADAR_TZ } from "@/lib/radar/queries";

export type RecapTheme = {
  title: string;
  narrative: string;
  item_ids: number[];
};

export type RecapStatus = "running" | "done" | "error";

/** The recap's identity — range plus quality gate. Mirrors the table's UNIQUE key. */
export type RecapKey = {
  since: string;
  until: string;
  minScore: number;
  novelOnly: boolean;
};

export type Recap = {
  status: RecapStatus;
  headline: string | null;
  themes: RecapTheme[];
  /** Items actually fed to the agent. */
  itemCount: number | null;
  /** Items that cleared the gate before the top-N cap. */
  consideredCount: number | null;
  error: string | null;
  /**
   * Analyses matching this range + gate that landed after the recap was built.
   * Non-zero means the panel should label the recap stale — never silently
   * regenerate, which would turn every visit to a live range into a minute of
   * local inference.
   */
  staleBy: number;
  /**
   * Subset of the cited ids whose `radar_items` row still exists. Citations
   * outside this set are rendered as plain text: `radar_recaps` deliberately
   * has no FK, so a recap outlives the 30-day sweep of its sources.
   */
  liveIds: number[];
};

type RecapRow = {
  status: RecapStatus;
  headline: string | null;
  themes: RecapTheme[] | null;
  item_count: number | null;
  considered_count: number | null;
  max_analyzed_at: string | null;
  error: string | null;
};

export async function getRecap(key: RecapKey): Promise<Recap | null> {
  const rows = await query<RecapRow>(
    `
      SELECT status, headline, themes, item_count, considered_count,
             max_analyzed_at::text, error
        FROM radar_recaps
       WHERE since = $1::date AND until = $2::date
         AND min_score = $3 AND novel_only = $4
       LIMIT 1
    `,
    [key.since, key.until, key.minScore, key.novelOnly],
  );
  const row = rows[0];
  if (!row) return null;

  const themes = row.themes ?? [];
  const [staleBy, liveIds] = await Promise.all([
    countAnalysesAfter(key, row.max_analyzed_at),
    resolveLiveIds(themes),
  ]);

  return {
    status: row.status,
    headline: row.headline,
    themes,
    itemCount: row.item_count,
    consideredCount: row.considered_count,
    error: row.error,
    staleBy,
    liveIds,
  };
}

/** Count kept analyses in this range + gate newer than the recap's watermark. */
async function countAnalysesAfter(
  key: RecapKey,
  watermark: string | null,
): Promise<number> {
  if (watermark === null) return 0;
  const rows = await query<{ n: string }>(
    `
      SELECT count(*)::text AS n
        FROM radar_analyses ra
       WHERE ra.verdict = 'keep'
         AND timezone($1, ra.analyzed_at)::date BETWEEN $2::date AND $3::date
         AND coalesce(ra.score, 0) >= $4
         AND ($5::boolean IS FALSE OR ra.dedup_status = 'novel')
         AND ra.analyzed_at > $6::timestamptz
    `,
    [RADAR_TZ, key.since, key.until, key.minScore, key.novelOnly, watermark],
  );
  return Number(rows[0]?.n ?? 0);
}

export type RecapSummary = RecapKey & {
  headline: string | null;
  itemCount: number | null;
  generatedAt: string;
};

type RecapSummaryRow = {
  since: string;
  until: string;
  min_score: number;
  novel_only: boolean;
  headline: string | null;
  item_count: number | null;
  generated_at: string;
};

/**
 * All completed recaps, newest range first — the browse list for reopening a
 * past recap. Only `done` rows: a `running` or `error` row has no headline
 * worth listing.
 */
export async function listRecaps(limit = 30): Promise<RecapSummary[]> {
  const rows = await query<RecapSummaryRow>(
    `
      SELECT since::text, until::text, min_score, novel_only,
             headline, item_count, generated_at::text
        FROM radar_recaps
       WHERE status = 'done'
       ORDER BY until DESC, since DESC, generated_at DESC
       LIMIT $1
    `,
    [limit],
  );
  return rows.map((row) => ({
    since: row.since,
    until: row.until,
    minScore: row.min_score,
    novelOnly: row.novel_only,
    headline: row.headline,
    itemCount: row.item_count,
    generatedAt: row.generated_at,
  }));
}

/** Which cited ids still resolve to a radar_items row. */
async function resolveLiveIds(themes: RecapTheme[]): Promise<number[]> {
  const cited = [...new Set(themes.flatMap((theme) => theme.item_ids ?? []))];
  if (cited.length === 0) return [];
  const rows = await query<{ id: string }>(
    "SELECT id FROM radar_items WHERE id = ANY($1::bigint[])",
    [cited],
  );
  return rows.map((row) => Number(row.id));
}
