"""Postgres I/O for ``radar_analyses`` and ``radar_pushed_topics``.

Short-lived ``psycopg`` connections, same posture as
``paca.collectors.info_radar.store``. Item fetching delegates to the
collector's ``query_unseen`` so the 30-day retention filter stays in one
place.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from paca.collectors.info_radar.store import query_unseen
from paca.core.db import database_url


def fetch_unseen_items(*, limit: int | None = None, source: str | None = None) -> list[dict]:
    """Return radar_items where seen_at IS NULL, oldest-first.

    Oldest-first so a single batch processes items in the order they came in
    — important when ``--limit`` truncates the batch. Within the 30-day
    retention window guaranteed by ``query_unseen``.
    """
    items = query_unseen(source=source, limit=limit if limit is not None else 1000)
    # query_unseen orders newest-first; reverse for FIFO processing.
    items = list(reversed(items))
    if limit is not None:
        items = items[:limit]
    return items


def insert_analysis(
    *,
    radar_item_id: int,
    verdict: str,
    tier1_reason: str | None = None,
    summary: str | None = None,
    impact_md: str | None = None,
    score: int | None = None,
    tags: list[str] | None = None,
    content_status: str | None = None,
    dedup_status: str | None = None,
    dedup_match_id: int | None = None,
) -> int | None:
    """Insert one radar_analyses row. Idempotent via UNIQUE(radar_item_id).

    Returns the new row id, or ``None`` if a row already existed.
    """
    sql = """
        INSERT INTO radar_analyses
            (radar_item_id, verdict, tier1_reason, summary, impact_md, score,
             tags, content_status, dedup_status, dedup_match_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (radar_item_id) DO NOTHING
        RETURNING id
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    radar_item_id,
                    verdict,
                    tier1_reason,
                    summary,
                    impact_md,
                    score,
                    Jsonb(tags or []),
                    content_status,
                    dedup_status,
                    dedup_match_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def mark_seen(radar_item_id: int) -> None:
    """Set radar_items.seen_at = now() for one row. Called by the analysis layer only."""
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE radar_items SET seen_at = now() WHERE id = %s",
                (radar_item_id,),
            )
        conn.commit()


def insert_topic(*, summary: str, embedding: list[float], item_id: int) -> int:
    """Insert a new radar_pushed_topics row. Returns the new id."""
    sql = """
        INSERT INTO radar_pushed_topics
            (topic_summary, embedding, item_ids)
        VALUES (%s, %s, %s::jsonb)
        RETURNING id
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (summary, _vec_literal(embedding), Jsonb([item_id])))
            row = cur.fetchone()
            assert row is not None
            new_id = row[0]
        conn.commit()
    return int(new_id)


def append_item_to_topic(*, topic_id: int, item_id: int) -> None:
    """Append item_id to an existing topic's item_ids JSONB array; bump last_seen_at."""
    sql = """
        UPDATE radar_pushed_topics
           SET item_ids = COALESCE(item_ids, '[]'::jsonb) || %s::jsonb,
               last_seen_at = now()
         WHERE id = %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (Jsonb([item_id]), topic_id))
        conn.commit()


def ann_search_topics(
    embedding: list[float],
    *,
    k: int = 5,
    threshold: float = 0.40,
) -> list[dict[str, Any]]:
    """Return up to ``k`` topics within ``threshold`` cosine distance.

    Result list is sorted by distance ascending (closest first). Each row is
    ``{id, topic_summary, distance}``.
    """
    sql = """
        SELECT id, topic_summary, embedding <=> %s::vector AS distance
          FROM radar_pushed_topics
         WHERE embedding <=> %s::vector < %s
         ORDER BY distance ASC
         LIMIT %s
    """
    vec = _vec_literal(embedding)
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (vec, vec, threshold, k))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _vec_literal(values: list[float]) -> str:
    """Format a Python list as the pgvector text literal ``"[v1,v2,...]"``.

    psycopg + pgvector accept this directly when cast with ``::vector``.
    """
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


__all__ = [
    "fetch_unseen_items",
    "insert_analysis",
    "mark_seen",
    "insert_topic",
    "append_item_to_topic",
    "ann_search_topics",
]
