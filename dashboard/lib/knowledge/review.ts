import { readFile } from "node:fs/promises";
import path from "node:path";

import matter from "gray-matter";

import { query } from "@/lib/db";
import { wikiRoot } from "@/lib/paths";
import { RADAR_TZ } from "@/lib/radar/queries";

/**
 * Fixed Ebbinghaus offsets, in days after `captured_at`. Mirrors
 * `paca.workflows.knowledge_review.STAGES` — the Python side is the source of
 * truth (and is where the arithmetic is unit-tested); this copy exists only so
 * the in-request "seen" advance can run without shelling out.
 */
export const REVIEW_STAGES = [1, 3, 7, 15, 30, 60, 120];

/** Cap on cards shown at once; overflow is reported as a remainder count. */
export const REVIEW_DISPLAY_CAP = 5;

export type ReviewCard = {
  docPath: string;
  title: string;
  /** The doc's own frontmatter `summary` (its `## 总结`), or a body fallback. */
  summary: string | null;
  /** YYYY-MM-DD capture anchor. */
  capturedAt: string;
  /** 0-based curve stage this review sits at. */
  stage: number;
  totalStages: number;
};

type DueRow = {
  doc_path: string;
  captured_at: string;
  stage: number;
};

const DUE_WHERE = `next_due_at IS NOT NULL
        AND next_due_at <= (timezone($1, now()))::date`;

/**
 * Docs due today (radar timezone), longest-overdue first, capped at
 * REVIEW_DISPLAY_CAP with the full due count returned for the remainder line.
 */
export async function getDueReviews(): Promise<{ cards: ReviewCard[]; total: number }> {
  const [rows, totals] = await Promise.all([
    query<DueRow>(
      `SELECT doc_path, captured_at::text, stage
         FROM knowledge_reviews
        WHERE ${DUE_WHERE}
        ORDER BY next_due_at ASC, captured_at ASC
        LIMIT $2`,
      [RADAR_TZ, REVIEW_DISPLAY_CAP],
    ),
    query<{ n: string }>(
      `SELECT count(*)::text AS n FROM knowledge_reviews WHERE ${DUE_WHERE}`,
      [RADAR_TZ],
    ),
  ]);

  const cards = await Promise.all(rows.map(rowToCard));
  return { cards, total: Number(totals[0]?.n ?? 0) };
}

async function rowToCard(row: DueRow): Promise<ReviewCard> {
  const meta = await readDocMeta(row.doc_path);
  return {
    docPath: row.doc_path,
    title: meta.title,
    summary: meta.summary,
    capturedAt: row.captured_at.slice(0, 10),
    stage: row.stage,
    totalStages: REVIEW_STAGES.length,
  };
}

/**
 * Frontmatter title + summary for a due doc. `summary` is the doc's own closing
 * summary (written to frontmatter and the `## 总结` section at ingest); for a
 * hand-created doc that has none, fall back to its first body paragraph.
 */
async function readDocMeta(
  docPath: string,
): Promise<{ title: string; summary: string | null }> {
  const fallbackTitle = path.basename(docPath, ".md");
  if (path.isAbsolute(docPath) || docPath.split(/[\\/]/).includes("..")) {
    return { title: fallbackTitle, summary: null };
  }
  try {
    const raw = await readFile(path.join(wikiRoot(), docPath), "utf8");
    const { data, content } = matter(raw);
    const title =
      typeof data.title === "string" && data.title.trim() ? data.title : fallbackTitle;
    const summary =
      typeof data.summary === "string" && data.summary.trim()
        ? data.summary.trim()
        : firstParagraph(content);
    return { title, summary };
  } catch {
    // file vanished between sync and render — sync will unenroll it
    return { title: fallbackTitle, summary: null };
  }
}

/** First prose paragraph of the body (skipping headings and the Related marker
 *  block), truncated — the fallback when a doc carries no frontmatter summary. */
function firstParagraph(body: string): string | null {
  for (const block of body.split(/\n\s*\n/)) {
    const text = block.trim();
    if (!text || text.startsWith("#") || text.startsWith("<!--")) continue;
    return text.length > 400 ? `${text.slice(0, 400)}…` : text;
  }
  return null;
}

/**
 * Advance one doc's review stage in a single statement. The fast-forward
 * (`max(stage + 1, stages-already-elapsed)`), retirement (`next_due_at = NULL`
 * past the final stage), and the radar-timezone "today" all live in SQL so this
 * matches `schedule_advance` in Python without re-deriving date math in JS.
 * `target` computes the new stage from the row (a normal join with `cfg`), then
 * the UPDATE joins to it — an UPDATE target cannot be referenced from a LATERAL
 * over its own FROM clause, so the arithmetic lives one CTE up.
 */
export async function advanceReview(docPath: string): Promise<void> {
  await query(
    `
    WITH cfg AS (
      SELECT $2::int[] AS stages, (timezone($1, now()))::date AS today
    ),
    target AS (
      SELECT kr.doc_path,
             GREATEST(
               kr.stage + 1,
               (SELECT count(*)::int FROM unnest(cfg.stages) s WHERE s <= (cfg.today - kr.captured_at))
             ) AS new_stage,
             kr.captured_at,
             cfg.stages AS stages
        FROM knowledge_reviews kr, cfg
       WHERE kr.doc_path = $3
    )
    UPDATE knowledge_reviews kr
       SET stage = t.new_stage,
           next_due_at = CASE
             WHEN t.new_stage >= array_length(t.stages, 1) THEN NULL
             ELSE t.captured_at + t.stages[t.new_stage + 1]
           END,
           last_reviewed_at = now()
      FROM target t
     WHERE kr.doc_path = t.doc_path
    `,
    [RADAR_TZ, REVIEW_STAGES, docPath],
  );
}
