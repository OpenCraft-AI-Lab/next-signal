"""Postgres I/O for ``knowledge_reviews``.

Short-lived ``psycopg`` connections, same posture as
``next_signal.workflows.info_radar_recap.store``. The timezone helpers are
re-exported from ``next_signal.core.clock`` so "today" means the same local day
across radar, review, and the scheduler.

Only reconciliation runs in Python — the dashboard reads due cards and advances
stages with its own SQL — so this store is enroll / unenroll / count_due plus
the shared "today".
"""

from __future__ import annotations

from typing import Any

import psycopg

from next_signal.core.clock import radar_timezone, today_local
from next_signal.core.db import database_url


def existing_doc_paths() -> set[str]:
    """Every ``doc_path`` currently enrolled."""
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT doc_path FROM knowledge_reviews")
            return {row[0] for row in cur.fetchall()}


def insert_seeded(rows: list[dict[str, Any]]) -> int:
    """Enroll new docs. ``ON CONFLICT DO NOTHING`` makes a racing sync a no-op.

    Each row: ``doc_path``, ``captured_at``, ``stage``, ``next_due_at``.
    """
    if not rows:
        return 0
    sql = """
        INSERT INTO knowledge_reviews (doc_path, captured_at, stage, next_due_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (doc_path) DO NOTHING
    """
    inserted = 0
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    sql, (r["doc_path"], r["captured_at"], r["stage"], r["next_due_at"])
                )
                inserted += cur.rowcount
        conn.commit()
    return inserted


def delete_paths(paths: list[str]) -> int:
    """Unenroll docs whose files are gone. Returns rows deleted."""
    if not paths:
        return 0
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM knowledge_reviews WHERE doc_path = ANY(%s)", (paths,)
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted


def count_due() -> int:
    """How many docs are due today (radar tz), retired rows excluded."""
    sql = """
        SELECT count(*) FROM knowledge_reviews
         WHERE next_due_at IS NOT NULL
           AND next_due_at <= (timezone(%s, now()))::date
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (radar_timezone(),))
            return int(cur.fetchone()[0])


__all__ = [
    "radar_timezone",
    "today_local",
    "existing_doc_paths",
    "insert_seeded",
    "delete_paths",
    "count_due",
]
