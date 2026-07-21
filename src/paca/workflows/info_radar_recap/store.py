"""Postgres I/O for ``radar_recaps``.

Short-lived ``psycopg`` connections, same posture as
``paca.workflows.info_radar_analysis.store``.

``impact_md`` is deliberately absent from the candidate projection: the recap
synthesizes across items, and the per-item deep dive would triple prompt size
for content the themes are meant to abstract away.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

from paca.core.db import database_url

# Matches dashboard/lib/radar/queries.ts so a recap range covers exactly the
# day rows the reader sees beneath it.
_DEFAULT_TZ = "America/Los_Angeles"


def radar_timezone() -> str:
    """Local timezone for day bucketing. Read at call time, not at import."""
    return os.environ.get("INFO_RADAR_TIMEZONE", "").strip() or _DEFAULT_TZ


def today_local() -> date:
    """Today in the radar timezone — the same 'today' the dashboard uses."""
    return datetime.now(ZoneInfo(radar_timezone())).date()


def select_candidates(
    *,
    since: date,
    until: date,
    min_score: int,
    novel_only: bool,
    cap: int,
) -> tuple[list[dict[str, Any]], int, datetime | None]:
    """Return ``(items, considered_count, max_analyzed_at)`` for one range+gate.

    ``items`` is capped at ``cap``, highest score first. The two window
    functions are evaluated over every row matching the gate — before ``LIMIT``
    truncates — so the caller learns the true match count and staleness
    watermark from the same query.
    """
    sql = """
        SELECT
            ri.id,
            ri.title,
            ra.score,
            ra.tags,
            ra.summary,
            count(*) OVER () AS considered_count,
            max(ra.analyzed_at) OVER () AS max_analyzed_at
        FROM radar_analyses ra
        JOIN radar_items ri ON ri.id = ra.radar_item_id
        WHERE ra.verdict = 'keep'
          AND timezone(%s, ra.analyzed_at)::date BETWEEN %s AND %s
          AND coalesce(ra.score, 0) >= %s
          AND (%s IS FALSE OR ra.dedup_status = 'novel')
        ORDER BY ra.score DESC NULLS LAST, ra.analyzed_at DESC
        LIMIT %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (radar_timezone(), since, until, min_score, novel_only, cap))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    if not rows:
        return [], 0, None

    considered = int(rows[0]["considered_count"])
    watermark = rows[0]["max_analyzed_at"]
    items = [
        {
            "id": int(r["id"]),
            "title": r["title"],
            "score": int(r["score"] or 0),
            "tags": r["tags"] or [],
            "summary": r["summary"] or "",
        }
        for r in rows
    ]
    return items, considered, watermark


def read_recap(
    *, since: date, until: date, min_score: int, novel_only: bool
) -> dict[str, Any] | None:
    """Return the stored recap row for one key, or ``None``."""
    sql = """
        SELECT id, since, until, min_score, novel_only, status, headline, themes,
               item_count, considered_count, max_analyzed_at, error, generated_at
          FROM radar_recaps
         WHERE since = %s AND until = %s AND min_score = %s AND novel_only = %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (since, until, min_score, novel_only))
            row = cur.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def begin_recap(*, since: date, until: date, min_score: int, novel_only: bool) -> bool:
    """Claim a key for generation. Returns False when one is already running.

    Existing ``headline`` / ``themes`` are left untouched so a regeneration that
    fails still leaves the previous recap readable. The ``WHERE`` on the
    conflict branch is what makes a concurrent trigger a no-op rather than a
    second generation.
    """
    sql = """
        INSERT INTO radar_recaps (since, until, min_score, novel_only, status)
        VALUES (%s, %s, %s, %s, 'running')
        ON CONFLICT (since, until, min_score, novel_only) DO UPDATE
            SET status = 'running', error = NULL, generated_at = now()
            WHERE radar_recaps.status <> 'running'
        RETURNING id
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (since, until, min_score, novel_only))
            claimed = cur.fetchone() is not None
        conn.commit()
    return claimed


def finish_recap(
    *,
    since: date,
    until: date,
    min_score: int,
    novel_only: bool,
    headline: str,
    themes: list[dict[str, Any]],
    item_count: int,
    considered_count: int,
    max_analyzed_at: datetime | None,
) -> None:
    """Store a successful recap and flip the row to ``done``."""
    sql = """
        UPDATE radar_recaps
           SET status = 'done',
               headline = %s,
               themes = %s::jsonb,
               item_count = %s,
               considered_count = %s,
               max_analyzed_at = %s,
               error = NULL,
               generated_at = now()
         WHERE since = %s AND until = %s AND min_score = %s AND novel_only = %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    headline,
                    Jsonb(themes),
                    item_count,
                    considered_count,
                    max_analyzed_at,
                    since,
                    until,
                    min_score,
                    novel_only,
                ),
            )
        conn.commit()


def fail_recap(
    *, since: date, until: date, min_score: int, novel_only: bool, error: str
) -> None:
    """Mark a recap failed. Prior content columns are intentionally untouched."""
    sql = """
        UPDATE radar_recaps
           SET status = 'error', error = %s
         WHERE since = %s AND until = %s AND min_score = %s AND novel_only = %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (error[:2000], since, until, min_score, novel_only))
        conn.commit()


__all__ = [
    "radar_timezone",
    "today_local",
    "select_candidates",
    "read_recap",
    "begin_recap",
    "finish_recap",
    "fail_recap",
]
