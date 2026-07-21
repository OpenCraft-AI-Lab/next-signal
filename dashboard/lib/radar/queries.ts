import { query } from "@/lib/db";
import { type Locale } from "@/lib/i18n/dictionaries";
import type { RadarFilters } from "@/lib/radar/filter-params";

export type DayGroup = {
  day: string;
  keptCount: number;
  medianScore: number | null;
  topTitle: string | null;
  topItems: DayGroupTopItem[];
};

export type DayGroupTopItem = {
  id: number;
  title: string;
  score: number;
  tags: string[];
};

export type RadarItem = {
  id: number;
  source: string;
  sourceId: string;
  sourceUrl: string | null;
  title: string;
  excerpt: string | null;
  publishedAt: string | null;
  fetchedAt: string;
  analyzedAt: string;
  tier1Reason: string | null;
  summary: string | null;
  impactMd: string | null;
  score: number;
  tags: string[];
  contentStatus: string | null;
  dedupStatus: string | null;
};

export type TrackerForDay = {
  date: string;
  pulledBySource: { source: string; n: number }[];
  pulledTotal: number;
  tier1: { kept: number; dropped: number };
  tier2: { ok: number; fallback: number; error: number };
  dedup: { novel: number; duplicate: number };
  hist: number[];
};

export type RadarItemDetail = RadarItem & {
  verdict: string | null;
  analysisId: number | null;
  dedupMatchId: number | null;
  duplicateTopicSummary: string | null;
};

export type DetailListItem = {
  id: number;
  title: string;
  score: number;
};

export const RADAR_TZ = process.env.INFO_RADAR_TIMEZONE ?? "America/Los_Angeles";

function toLocalDay(date: Date): string {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: RADAR_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day}`;
}

function coerceTags(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((tag): tag is string => typeof tag === "string") : [];
}

function normalizeItem(row: RadarItemRow): RadarItem {
  return {
    id: Number(row.id),
    source: row.source,
    sourceId: row.source_id,
    sourceUrl: row.source_url,
    title: row.title,
    excerpt: row.excerpt,
    publishedAt: row.published_at,
    fetchedAt: row.fetched_at,
    analyzedAt: row.analyzed_at,
    tier1Reason: row.tier1_reason,
    summary: row.summary,
    impactMd: row.impact_md,
    score: Number(row.score ?? 0),
    tags: coerceTags(row.tags),
    contentStatus: row.content_status,
    dedupStatus: row.dedup_status,
  };
}

type DayGroupRow = {
  day: string;
  kept_count: string;
  median_score: string | null;
  top_title: string | null;
  top_items: { id: string | number; title: string; score: number | null; tags: unknown }[] | null;
};

type RadarItemRow = {
  id: string;
  source: string;
  source_id: string;
  source_url: string | null;
  title: string;
  excerpt: string | null;
  published_at: string | null;
  fetched_at: string;
  analyzed_at: string;
  tier1_reason: string | null;
  summary: string | null;
  impact_md: string | null;
  score: number | null;
  tags: unknown;
  content_status: string | null;
  dedup_status: string | null;
};

type TrackerCountRow = { label: string; n: string };
type HistRow = { bucket: number; n: string };
type DetailRow = RadarItemRow & {
  verdict: string | null;
  analysis_id: string | null;
  dedup_match_id: string | null;
  duplicate_topic_summary: string | null;
};
type DetailListRow = { id: string; title: string; score: number | null };

export function todayInRadarTz(): string {
  return toLocalDay(new Date());
}

export function displayDay(day: string, locale: Locale = "en"): string {
  return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en", {
    timeZone: "UTC",
    month: locale === "zh" ? "numeric" : "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${day}T00:00:00Z`));
}

export async function getDayGroups(daysBack: number): Promise<DayGroup[]> {
  const today = todayInRadarTz();
  // Top-3 items are folded into the same query via a LATERAL subquery so
  // /radar avoids the per-day N+1 it used to do (one full getItemsForDay
  // call per past day just to .slice(0, 3) the result).
  const rows = await query<DayGroupRow>(
    `
      WITH per_day AS (
        SELECT
          timezone($1, ra.analyzed_at)::date AS day_local,
          ra.score,
          ra.analyzed_at,
          ra.tags,
          ri.id,
          ri.title
        FROM radar_analyses ra
        JOIN radar_items ri ON ri.id = ra.radar_item_id
        WHERE ra.verdict = 'keep'
          AND timezone($1, ra.analyzed_at)::date < $2::date
          AND timezone($1, ra.analyzed_at)::date >= ($2::date - ($3::int * interval '1 day'))
      ),
      ranked AS (
        SELECT *,
          row_number() OVER (
            PARTITION BY day_local
            ORDER BY score DESC NULLS LAST, analyzed_at DESC
          ) AS rn
        FROM per_day
      )
      SELECT
        to_char(p.day_local, 'YYYY-MM-DD') AS day,
        count(*) AS kept_count,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY p.score) AS median_score,
        (array_agg(p.title ORDER BY p.score DESC NULLS LAST, p.analyzed_at DESC))[1] AS top_title,
        coalesce(
          (SELECT jsonb_agg(jsonb_build_object(
            'id', r.id, 'title', r.title, 'score', r.score, 'tags', r.tags
          ) ORDER BY r.rn)
           FROM ranked r WHERE r.day_local = p.day_local AND r.rn <= 3),
          '[]'::jsonb
        ) AS top_items
      FROM per_day p
      GROUP BY p.day_local
      ORDER BY p.day_local DESC
    `,
    [RADAR_TZ, today, daysBack],
  );
  return rows.map((row) => ({
    day: row.day,
    keptCount: Number(row.kept_count),
    medianScore: row.median_score == null ? null : Math.round(Number(row.median_score)),
    topTitle: row.top_title,
    topItems: (row.top_items ?? []).map((item) => ({
      id: Number(item.id),
      title: item.title,
      score: Number(item.score ?? 0),
      tags: coerceTags(item.tags),
    })),
  }));
}

export async function getItemsForDay(
  day: string,
  filters: RadarFilters,
  runStart: Date | null = null,
): Promise<RadarItem[]> {
  const rows = await query<RadarItemRow>(
    `
      SELECT
        ri.id,
        ri.source,
        ri.source_id,
        ri.url AS source_url,
        ri.title,
        ri.excerpt,
        ri.published_at::text,
        ri.fetched_at::text,
        ra.analyzed_at::text,
        ra.tier1_reason,
        ra.summary,
        ra.impact_md,
        ra.score,
        ra.tags,
        ra.content_status,
        ra.dedup_status
      FROM radar_analyses ra
      JOIN radar_items ri ON ri.id = ra.radar_item_id
      WHERE ra.verdict = 'keep'
        AND timezone($1, ra.analyzed_at)::date = $2::date
        AND coalesce(ra.score, 0) >= $3
        AND ($4::boolean IS FALSE OR ra.dedup_status = 'novel')
        AND ($6::timestamptz IS NULL OR ra.analyzed_at >= $6::timestamptz)
      ORDER BY
        CASE WHEN $5 = 'score-asc' THEN ra.score END ASC NULLS LAST,
        CASE WHEN $5 = 'newest' THEN coalesce(ri.published_at, ri.fetched_at) END DESC NULLS LAST,
        CASE WHEN $5 = 'score-desc' THEN ra.score END DESC NULLS LAST,
        ra.analyzed_at DESC,
        ri.id DESC
    `,
    [
      RADAR_TZ,
      day,
      filters.minScore,
      filters.novelOnly,
      filters.sort,
      runStart === null ? null : runStart.toISOString(),
    ],
  );
  return rows.map(normalizeItem);
}

export async function getTrackerForDay(
  day: string,
  bounds: { analyzeStart?: Date | null; pullStart?: Date | null } = {},
): Promise<TrackerForDay> {
  // `analyzeStart` clamps every analysis-side count (tier1 / tier2 / dedup /
  // histogram) to `analyzed_at >= analyzeStart`. `pullStart` clamps the
  // `pulled_by_source` row to `fetched_at >= pullStart`. Both are emitted
  // by the "Last feed" filter (which captures one click's worth of work).
  const analyzeStartIso = bounds.analyzeStart?.toISOString() ?? null;
  const pullStartIso = bounds.pullStart?.toISOString() ?? null;
  const [sourceRows, tier1Rows, tier2Rows, dedupRows, histRows] = await Promise.all([
    query<TrackerCountRow>(
      `
        SELECT source AS label, count(*) AS n
        FROM radar_items
        WHERE timezone($1, fetched_at)::date = $2::date
          AND ($3::timestamptz IS NULL OR fetched_at >= $3::timestamptz)
        GROUP BY source
        ORDER BY source
      `,
      [RADAR_TZ, day, pullStartIso],
    ),
    query<TrackerCountRow>(
      `
        SELECT verdict AS label, count(*) AS n
        FROM radar_analyses
        WHERE timezone($1, analyzed_at)::date = $2::date
          AND ($3::timestamptz IS NULL OR analyzed_at >= $3::timestamptz)
        GROUP BY verdict
      `,
      [RADAR_TZ, day, analyzeStartIso],
    ),
    query<TrackerCountRow>(
      `
        SELECT content_status AS label, count(*) AS n
        FROM radar_analyses
        WHERE verdict = 'keep'
          AND content_status IS NOT NULL
          AND timezone($1, analyzed_at)::date = $2::date
          AND ($3::timestamptz IS NULL OR analyzed_at >= $3::timestamptz)
        GROUP BY content_status
      `,
      [RADAR_TZ, day, analyzeStartIso],
    ),
    query<TrackerCountRow>(
      `
        SELECT dedup_status AS label, count(*) AS n
        FROM radar_analyses
        WHERE verdict = 'keep'
          AND dedup_status IS NOT NULL
          AND timezone($1, analyzed_at)::date = $2::date
          AND ($3::timestamptz IS NULL OR analyzed_at >= $3::timestamptz)
        GROUP BY dedup_status
      `,
      [RADAR_TZ, day, analyzeStartIso],
    ),
    query<HistRow>(
      `
        SELECT least(floor(score / 10), 10)::int AS bucket, count(*) AS n
        FROM radar_analyses
        WHERE verdict = 'keep'
          AND score IS NOT NULL
          AND timezone($1, analyzed_at)::date = $2::date
          AND ($3::timestamptz IS NULL OR analyzed_at >= $3::timestamptz)
        GROUP BY bucket
        ORDER BY bucket
      `,
      [RADAR_TZ, day, analyzeStartIso],
    ),
  ]);

  const countByLabel = (rows: TrackerCountRow[], label: string) =>
    Number(rows.find((row) => row.label === label)?.n ?? 0);
  const hist = Array.from({ length: 11 }, () => 0);
  for (const row of histRows) hist[row.bucket] = Number(row.n);
  const pulledBySource = sourceRows.map((row) => ({ source: row.label, n: Number(row.n) }));

  return {
    date: day,
    pulledBySource,
    pulledTotal: pulledBySource.reduce((sum, source) => sum + source.n, 0),
    tier1: { kept: countByLabel(tier1Rows, "keep"), dropped: countByLabel(tier1Rows, "drop") },
    tier2: {
      ok: countByLabel(tier2Rows, "full"),
      fallback: countByLabel(tier2Rows, "fallback"),
      error: countByLabel(tier2Rows, "error"),
    },
    dedup: {
      novel: countByLabel(dedupRows, "novel"),
      duplicate: countByLabel(dedupRows, "duplicate"),
    },
    hist,
  };
}

export async function getItemDetail(itemId: number): Promise<RadarItemDetail | null> {
  const rows = await query<DetailRow>(
    `
      SELECT
        ri.id,
        ri.source,
        ri.source_id,
        ri.url AS source_url,
        ri.title,
        ri.excerpt,
        ri.published_at::text,
        ri.fetched_at::text,
        ra.analyzed_at::text,
        ra.tier1_reason,
        ra.summary,
        ra.impact_md,
        ra.score,
        ra.tags,
        ra.content_status,
        ra.dedup_status,
        ra.verdict,
        ra.id AS analysis_id,
        ra.dedup_match_id,
        rpt.topic_summary AS duplicate_topic_summary
      FROM radar_items ri
      LEFT JOIN radar_analyses ra ON ra.radar_item_id = ri.id
      LEFT JOIN radar_pushed_topics rpt ON rpt.id = ra.dedup_match_id
      WHERE ri.id = $1
      LIMIT 1
    `,
    [itemId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    ...normalizeItem({
      ...row,
      analyzed_at: row.analyzed_at ?? "",
      score: row.score ?? 0,
      tags: row.tags ?? [],
    }),
    verdict: row.verdict,
    analysisId: row.analysis_id == null ? null : Number(row.analysis_id),
    dedupMatchId: row.dedup_match_id == null ? null : Number(row.dedup_match_id),
    duplicateTopicSummary: row.duplicate_topic_summary,
  };
}

/**
 * Identify the start of the most recent contiguous cluster of timestamps
 * in `column` on `day` (local) — rows whose consecutive gap is ≤ 5 minutes
 * are treated as one operator-triggered run. Returns the cluster's
 * earliest timestamp, suitable for use as a filter cutoff.
 *
 * Used for both `analyzed_at` (a single analyze pass) and `fetched_at`
 * (a single pull pass). Caller passes the unsafe column name — it's
 * checked against a whitelist to keep this still a parameterized query.
 */
async function getLatestClusterStart(
  day: string,
  column: "analyzed_at" | "fetched_at",
  table: "radar_analyses" | "radar_items",
): Promise<Date | null> {
  const rows = await query<{ run_start: string | null }>(
    `
      WITH ordered AS (
        SELECT ${column} AS ts,
               lag(${column}) OVER (ORDER BY ${column}) AS prev_at
        FROM ${table}
        WHERE timezone($1, ${column})::date = $2::date
      ),
      flagged AS (
        SELECT ts,
               CASE
                 WHEN prev_at IS NULL OR ts - prev_at > interval '5 minutes' THEN 1
                 ELSE 0
               END AS new_run
        FROM ordered
      ),
      runs AS (
        SELECT ts,
               sum(new_run) OVER (ORDER BY ts ROWS UNBOUNDED PRECEDING) AS run_id
        FROM flagged
      )
      SELECT min(ts)::text AS run_start
      FROM runs
      WHERE run_id = (SELECT max(run_id) FROM runs)
    `,
    [RADAR_TZ, day],
  );
  const iso = rows[0]?.run_start ?? null;
  return iso === null ? null : new Date(iso);
}

/** Start of the latest `analyze` cluster (5-min gap heuristic) for `day`. */
export function getLatestAnalyzeStart(day: string): Promise<Date | null> {
  return getLatestClusterStart(day, "analyzed_at", "radar_analyses");
}

/** Start of the latest `pull` cluster (5-min gap heuristic) for `day`. */
export function getLatestPullStart(day: string): Promise<Date | null> {
  return getLatestClusterStart(day, "fetched_at", "radar_items");
}

function stateDate(value: string | null): Date | null {
  if (value === null) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export type LastFeedBounds = {
  analyzeStart: Date | null;
  pullStart: Date | null;
};

/**
 * Timestamp bounds for the operator's latest dashboard-triggered feed.
 * Prefer run-state click timestamps so a 0-result click doesn't fall back
 * to stale DB clusters from a previous feed.
 */
export async function getLastFeedBounds(day: string): Promise<LastFeedBounds> {
  const { getRunState } = await import("@/lib/radar/run-state");
  const runState = await getRunState();
  const analyzeStart = stateDate(runState.lastAnalyzeAt);
  const pullStart =
    stateDate(runState.lastPullStartAt) ??
    (runState.lastPullNew === 0 ? stateDate(runState.lastPullAt) : null);

  if (analyzeStart !== null && pullStart !== null) {
    return { analyzeStart, pullStart };
  }

  const [fallbackAnalyzeStart, fallbackPullStart] = await Promise.all([
    analyzeStart === null ? getLatestAnalyzeStart(day) : Promise.resolve(null),
    pullStart === null ? getLatestPullStart(day) : Promise.resolve(null),
  ]);

  return {
    analyzeStart: analyzeStart ?? fallbackAnalyzeStart,
    pullStart: pullStart ?? fallbackPullStart,
  };
}

export type LastFeedSummary = {
  pull: {
    /**
     * ISO timestamp of the most recent operator click that triggered a pull.
     * Read from `radar-state.json` written by `runPullAndAnalyze`. Falls
     * back to MAX(`fetched_at`) if the state file is missing (e.g. operator
     * has never clicked through the dashboard).
     */
    latestAt: string | null;
    /**
     * Number of new rows inserted by the most recent click's pull. When
     * the click had no new content, this is 0 — distinguishing "operator
     * clicked recently and got nothing" from "no click in a while".
     */
    count: number;
  };
  analyze: {
    /** ISO timestamp of the most recent analyze-phase spawn (click time). */
    latestAt: string | null;
    /** Number of rows in the latest analyze cluster (5-min gap). */
    count: number;
  };
  /**
   * Count of radar_items still awaiting analysis (`seen_at IS NULL`), across
   * the whole table. 0 means the analyzer has caught up with the collector.
   */
  unanalyzed: number;
};

/**
 * Build the summary for the nav chips beside `Pull + Analyze`. The DB
 * gives us "what got written" (cluster timestamps + counts) and
 * `radar-state.json` gives us "when did the operator click" — combining
 * both is how a 0-result click stays visible in the UI.
 *
 * The DB side computes latest pull/analyze cluster starts via window
 * functions and counts the rows belonging to those clusters in the same
 * query. Spans the whole table (not a single day) so the chip stays
 * accurate across midnight boundaries.
 */
export async function getLastFeedSummary(): Promise<LastFeedSummary> {
  const { getRunState } = await import("@/lib/radar/run-state");
  const runState = await getRunState();
  const rows = await query<{
    last_fetched: string | null;
    pull_cluster_start: string | null;
    pull_count: string;
    last_analyzed: string | null;
    analyze_cluster_start: string | null;
    analyze_count: string;
    unanalyzed: string;
  }>(
    `
      WITH pull_ordered AS (
        SELECT fetched_at AS ts,
               lag(fetched_at) OVER (ORDER BY fetched_at) AS prev_at
        FROM radar_items
        WHERE fetched_at >= now() - interval '7 days'
      ),
      pull_runs AS (
        SELECT ts,
               sum(CASE WHEN prev_at IS NULL OR ts - prev_at > interval '5 minutes' THEN 1 ELSE 0 END)
                 OVER (ORDER BY ts ROWS UNBOUNDED PRECEDING) AS run_id
        FROM pull_ordered
      ),
      analyze_ordered AS (
        SELECT analyzed_at AS ts,
               lag(analyzed_at) OVER (ORDER BY analyzed_at) AS prev_at
        FROM radar_analyses
        WHERE analyzed_at >= now() - interval '7 days'
      ),
      analyze_runs AS (
        SELECT ts,
               sum(CASE WHEN prev_at IS NULL OR ts - prev_at > interval '5 minutes' THEN 1 ELSE 0 END)
                 OVER (ORDER BY ts ROWS UNBOUNDED PRECEDING) AS run_id
        FROM analyze_ordered
      )
      SELECT
        (SELECT max(ts)::text FROM pull_runs) AS last_fetched,
        (SELECT min(ts)::text FROM pull_runs WHERE run_id = (SELECT max(run_id) FROM pull_runs)) AS pull_cluster_start,
        (SELECT count(*)::text FROM pull_runs WHERE run_id = (SELECT max(run_id) FROM pull_runs)) AS pull_count,
        (SELECT max(ts)::text FROM analyze_runs) AS last_analyzed,
        (SELECT min(ts)::text FROM analyze_runs WHERE run_id = (SELECT max(run_id) FROM analyze_runs)) AS analyze_cluster_start,
        (SELECT count(*)::text FROM analyze_runs WHERE run_id = (SELECT max(run_id) FROM analyze_runs)) AS analyze_count,
        (SELECT count(*)::text FROM radar_items WHERE seen_at IS NULL) AS unanalyzed
    `,
  );
  const row = rows[0];
  // Prefer the click timestamp from run-state.json — it reflects the
  // operator's most recent intent. The DB fallback (max fetched_at /
  // analyzed_at) only kicks in when the state file is missing, e.g.
  // first dashboard run, log rotation, or a manual `paca info-radar`
  // CLI invocation outside the dashboard.
  if (!row) {
    return {
      pull: { latestAt: runState.lastPullAt, count: runState.lastPullNew },
      analyze: { latestAt: runState.lastAnalyzeAt, count: 0 },
      unanalyzed: 0,
    };
  }
  return {
    pull: {
      latestAt: runState.lastPullAt ?? row.last_fetched,
      // When we have a click record, trust its count (0 is meaningful).
      count: runState.lastPullAt !== null ? runState.lastPullNew : Number(row.pull_count ?? 0),
    },
    analyze: {
      latestAt: runState.lastAnalyzeAt ?? row.last_analyzed,
      count:
        runState.lastAnalyzeAt !== null
          ? await getAnalyzeCountSince(runState.lastAnalyzeAt)
          : Number(row.analyze_count ?? 0),
    },
    unanalyzed: Number(row.unanalyzed ?? 0),
  };
}

async function getAnalyzeCountSince(start: string): Promise<number> {
  const rows = await query<{ count: string }>(
    `
      SELECT count(*)::text AS count
      FROM radar_analyses
      WHERE analyzed_at >= $1::timestamptz
    `,
    [start],
  );
  return Number(rows[0]?.count ?? 0);
}

export async function getFilteredTodayList(
  filters: RadarFilters,
  runStart: Date | null = null,
  dayOverride: string | null = null,
): Promise<DetailListItem[]> {
  const day = dayOverride ?? todayInRadarTz();
  const rows = await query<DetailListRow>(
    `
      SELECT ri.id, ri.title, ra.score
      FROM radar_analyses ra
      JOIN radar_items ri ON ri.id = ra.radar_item_id
      WHERE ra.verdict = 'keep'
        AND timezone($1, ra.analyzed_at)::date = $2::date
        AND coalesce(ra.score, 0) >= $3
        AND ($4::boolean IS FALSE OR ra.dedup_status = 'novel')
        AND ($6::timestamptz IS NULL OR ra.analyzed_at >= $6::timestamptz)
      ORDER BY
        CASE WHEN $5 = 'score-asc' THEN ra.score END ASC NULLS LAST,
        CASE WHEN $5 = 'newest' THEN coalesce(ri.published_at, ri.fetched_at) END DESC NULLS LAST,
        CASE WHEN $5 = 'score-desc' THEN ra.score END DESC NULLS LAST,
        ra.analyzed_at DESC,
        ri.id DESC
    `,
    [
      RADAR_TZ,
      day,
      filters.minScore,
      filters.novelOnly,
      filters.sort,
      runStart === null ? null : runStart.toISOString(),
    ],
  );
  return rows.map((row) => ({
    id: Number(row.id),
    title: row.title,
    score: Number(row.score ?? 0),
  }));
}
