"""Single Postgres + pgvector connection used by AgentOS and our own tables.

The database URL is read from ``DATABASE_URL`` env var. agno's PostgresDb will
auto-provision its own tables (sessions, memory, knowledge, traces). We add the
info-radar business tables in ``scripts/bootstrap_db.py``.
"""

from __future__ import annotations

import os
from functools import lru_cache

from agno.db.postgres import PostgresDb

# Columns the runtime reads or writes on each business table. The check is a
# subset test, so a newly added column needs no entry here — only a rename or a
# removal does. agno's own tables (sessions / memory / knowledge / traces) are
# out of scope: agno provisions them itself.
#
# This exists because a schema change that ships in the DDL but never reaches a
# running database is invisible. `radar_analyses.title` shipped, the stack kept
# running a pre-migration image, and the only symptom was `/radar` returning 500
# while `next-signal doctor` still reported Postgres healthy. Checked by `next-signal doctor`
# and asserted by `scripts/bootstrap_db.py` right after it applies the DDL.
BUSINESS_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "radar_items": frozenset(
        {"id", "source", "source_id", "url", "title", "excerpt", "published_at",
         "fetched_at", "seen_at", "payload"}
    ),
    "radar_analyses": frozenset(
        {"id", "radar_item_id", "verdict", "tier1_reason", "title", "summary",
         "impact_md", "score", "tags", "content_status", "dedup_status",
         "dedup_match_id", "pushed_at", "analyzed_at"}
    ),
    "radar_pushed_topics": frozenset(
        {"id", "topic_summary", "embedding", "embedder", "item_ids", "first_seen_at",
         "last_seen_at"}
    ),
    "radar_recaps": frozenset(
        {"id", "since", "until", "min_score", "novel_only", "status", "headline",
         "themes", "item_count", "considered_count", "max_analyzed_at", "error",
         "generated_at"}
    ),
    "knowledge_reviews": frozenset(
        {"id", "doc_path", "captured_at", "stage", "next_due_at", "last_reviewed_at",
         "created_at"}
    ),
    "schedule_state": frozenset(
        {"job", "last_slot_at", "last_run_at", "last_status", "last_error"}
    ),
}


def missing_business_columns(conn) -> dict[str, list[str]]:
    """Tables whose live columns don't cover BUSINESS_TABLE_COLUMNS, worst first.

    A missing table reports its whole expected set. Takes an open connection so
    the caller owns connection policy — `next-signal doctor` already has one open.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            (list(BUSINESS_TABLE_COLUMNS),),
        )
        live: dict[str, set[str]] = {}
        for table, column in cur.fetchall():
            live.setdefault(table, set()).add(column)
    missing = {
        table: sorted(expected - live.get(table, set()))
        for table, expected in BUSINESS_TABLE_COLUMNS.items()
    }
    return {t: cols for t, cols in missing.items() if cols}


def database_url(*, for_sqlalchemy: bool = False) -> str:
    """Return DATABASE_URL.

    SQLAlchemy's default driver for ``postgresql://`` is ``psycopg2``; we use
    ``psycopg`` (v3) instead. When ``for_sqlalchemy=True`` we rewrite the
    scheme to ``postgresql+psycopg://`` so SQLAlchemy picks the right driver
    while users keep a normal Postgres URL in their .env.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Example: "
            "postgresql://localhost:5432/next_signal"
        )
    if for_sqlalchemy and url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@lru_cache(maxsize=1)
def get_db() -> PostgresDb:
    """Return a process-wide singleton PostgresDb instance."""
    return PostgresDb(db_url=database_url(for_sqlalchemy=True))
