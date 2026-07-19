"""Postgres I/O for ``radar_items``.

Short-lived ``psycopg`` connections, like the rest of the business-table code
path. 30-day retention is enforced
both at write time (``sweep_expired``) and at read time (query helpers always
AND ``fetched_at > now() - interval '30 days'``).
"""

from __future__ import annotations

from typing import Iterable

import psycopg
from psycopg.types.json import Jsonb

from paca.collectors.info_radar.schema import RadarItem
from paca.core.db import database_url

_RETENTION_INTERVAL = "30 days"


def upsert_items(source: str, items: Iterable[RadarItem]) -> tuple[int, int]:
    """Insert items; skip on (source, source_id) conflict.

    Returns ``(written, skipped)``. The single SQL statement uses
    ``ON CONFLICT DO NOTHING`` so we never read-modify-write.
    """
    items = list(items)
    if not items:
        return (0, 0)

    sql = """
        INSERT INTO radar_items
            (source, source_id, url, title, excerpt, published_at, payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source, source_id) DO NOTHING
        RETURNING id
    """
    written = 0
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    sql,
                    (
                        source,
                        item.source_id,
                        item.url,
                        item.title,
                        item.excerpt,
                        item.published_at,
                        Jsonb(item.payload),
                    ),
                )
                if cur.fetchone() is not None:
                    written += 1
        conn.commit()
    return (written, len(items) - written)


def sweep_expired() -> int:
    """Delete rows whose ``fetched_at`` is older than 30 days. Returns row count."""
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM radar_items WHERE fetched_at < now() - %s::interval",
                (_RETENTION_INTERVAL,),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted


def query_recent(
    *, source: str | None = None, limit: int = 100
) -> list[dict]:
    """Return recent items (within retention window). For debugging / dashboards."""
    sql = """
        SELECT id, source, source_id, url, title, excerpt,
               published_at, fetched_at, seen_at, payload
          FROM radar_items
         WHERE fetched_at > now() - %s::interval
           {source_filter}
         ORDER BY COALESCE(published_at, fetched_at) DESC
         LIMIT %s
    """.format(source_filter="AND source = %s" if source else "")
    params: tuple = (
        (_RETENTION_INTERVAL, source, limit) if source else (_RETENTION_INTERVAL, limit)
    )
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def query_unseen(*, source: str | None = None, limit: int = 100) -> list[dict]:
    """Return unseen items (``seen_at IS NULL``) within retention window."""
    sql = """
        SELECT id, source, source_id, url, title, excerpt,
               published_at, fetched_at, payload
          FROM radar_items
         WHERE fetched_at > now() - %s::interval
           AND seen_at IS NULL
           {source_filter}
         ORDER BY COALESCE(published_at, fetched_at) DESC
         LIMIT %s
    """.format(source_filter="AND source = %s" if source else "")
    params: tuple = (
        (_RETENTION_INTERVAL, source, limit) if source else (_RETENTION_INTERVAL, limit)
    )
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


__all__ = ["upsert_items", "sweep_expired", "query_recent", "query_unseen"]
