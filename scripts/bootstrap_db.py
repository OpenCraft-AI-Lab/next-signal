"""One-time database setup: create the database (if absent), enable pgvector,
and create the custom tables that AgentOS doesn't manage for us.

agno's PostgresDb auto-provisions sessions / memory / knowledge / traces on
first use, so we don't touch those here — only the info-radar business tables.

Usage::

    DATABASE_URL=postgresql://localhost/next_signal uv run python scripts/bootstrap_db.py
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import psycopg
from psycopg import sql

from next_signal.core.db import missing_business_columns

CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector"

# next_signal.collectors.info_radar state.
CREATE_RADAR_ITEMS = """
CREATE TABLE IF NOT EXISTS radar_items (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    url             TEXT,
    title           TEXT NOT NULL,
    excerpt         TEXT,
    published_at    TIMESTAMPTZ,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    seen_at         TIMESTAMPTZ,
    payload         JSONB NOT NULL,
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS radar_items_fetched_at_idx ON radar_items (fetched_at);
CREATE INDEX IF NOT EXISTS radar_items_unseen_idx ON radar_items (fetched_at) WHERE seen_at IS NULL;
"""

# next_signal.workflows.info_radar_analysis: long-term memory of pushed topics so the
# dedup gate can detect a paraphrase of something already presented.
#
# `embedder` is the vector space a row belongs to — vectors from two embedders
# are not comparable even at equal width, so every search filters on it first.
# The column width stays 1024 across provider switches because
# next_signal.core.models.get_embedder rejects any other length outright.
CREATE_RADAR_PUSHED_TOPICS = """
CREATE TABLE IF NOT EXISTS radar_pushed_topics (
    id              BIGSERIAL PRIMARY KEY,
    topic_summary   TEXT NOT NULL,
    embedding       vector(1024) NOT NULL,
    embedder        TEXT NOT NULL,
    item_ids        JSONB NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- `embedder` shipped after this table did. Rows written before it exist cannot
-- be attributed: `embedders.local.model_id` has always been operator-editable,
-- so assuming the shipped default would mislabel a customized install and
-- recreate the cross-space comparison this column exists to prevent. They get a
-- sentinel no live provider matches, which retains the vectors while excluding
-- them from search. An operator who independently knows their provenance can
-- relabel them with one UPDATE — see docs/operations.md. The default is dropped
-- immediately afterwards so no future insert can omit provenance.
ALTER TABLE radar_pushed_topics
    ADD COLUMN IF NOT EXISTS embedder TEXT NOT NULL DEFAULT 'legacy:unknown';
ALTER TABLE radar_pushed_topics ALTER COLUMN embedder DROP DEFAULT;
-- The former IVFFlat index spanned every vector space at once. An approximate
-- index filters *after* candidate generation, so shared centroids let one
-- space degrade another's recall. At this table's hundreds-to-low-thousands
-- scale an exact scan of one identity's rows is cheap and has perfect recall.
DROP INDEX IF EXISTS radar_pushed_topics_embedding_idx;
CREATE INDEX IF NOT EXISTS radar_pushed_topics_embedder_idx
    ON radar_pushed_topics (embedder);
"""

# next_signal.workflows.info_radar_analysis: one row per radar_items row that's been
# through the analysis pipeline. UNIQUE(radar_item_id) makes re-runs idempotent.
# ON DELETE CASCADE: when the 30-day sweep drops a radar_items row, its
# analysis row goes with it (analysis is downstream-bounded).
CREATE_RADAR_ANALYSES = """
CREATE TABLE IF NOT EXISTS radar_analyses (
    id              BIGSERIAL PRIMARY KEY,
    radar_item_id   BIGINT NOT NULL REFERENCES radar_items(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL,            -- 'drop' | 'keep'
    tier1_reason    TEXT,
    title           TEXT,                     -- tier-2's rewritten title, NULL on 'drop'
    summary         TEXT,
    impact_md       TEXT,
    score           INTEGER,
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_status  TEXT,                     -- 'full' | 'fallback' | 'error' | NULL
    dedup_status    TEXT,                     -- 'novel' | 'duplicate' | NULL
    dedup_match_id  BIGINT REFERENCES radar_pushed_topics(id) ON DELETE SET NULL,
    pushed_at       TIMESTAMPTZ,
    analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (radar_item_id)
);
-- `title` shipped after this table did (output-language-policy); the CREATE
-- above only runs on a fresh database, so an already-provisioned one needs
-- this too. Nullable: historical rows keep NULL, and the dashboard falls
-- back to radar_items.title for them.
ALTER TABLE radar_analyses ADD COLUMN IF NOT EXISTS title TEXT;
CREATE INDEX IF NOT EXISTS radar_analyses_unpushed_idx
    ON radar_analyses (analyzed_at)
    WHERE verdict='keep' AND dedup_status='novel' AND pushed_at IS NULL;
"""

# next_signal.workflows.info_radar_recap: one cached recap per (range, quality gate).
# The UNIQUE key is the recap's identity, so a repeat request is a cache hit and
# a regenerate is an in-place upsert.
#
# Deliberately NO foreign key to radar_items: citation ids live inside `themes`
# so a recap survives the 30-day sweep. A recap is a point-in-time artifact and
# is expected to outlive its sources; readers render a citation whose item is
# gone as plain text.
CREATE_RADAR_RECAPS = """
CREATE TABLE IF NOT EXISTS radar_recaps (
    id               BIGSERIAL PRIMARY KEY,
    since            DATE NOT NULL,
    until            DATE NOT NULL,
    min_score        INTEGER NOT NULL DEFAULT 0,
    novel_only       BOOLEAN NOT NULL DEFAULT FALSE,
    status           TEXT NOT NULL,            -- 'running' | 'done' | 'error'
    headline         TEXT,
    themes           JSONB NOT NULL DEFAULT '[]'::jsonb,
    item_count       INTEGER,                  -- rows actually sent to the agent
    considered_count INTEGER,                  -- rows clearing the gate before the cap
    max_analyzed_at  TIMESTAMPTZ,              -- staleness watermark
    error            TEXT,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (since, until, min_score, novel_only)
);
"""

# next_signal.workflows.knowledge_review: one row per wiki doc, scheduling it back onto
# the reader's screen along a fixed Ebbinghaus curve. `doc_path` is the
# wiki-root-relative path — the same identity the ingest manifest uses — so
# reconciliation, not a foreign key, keeps the table and the filesystem tree in
# sync (the wiki is not a table). `next_due_at IS NULL` means the doc advanced
# past the final stage and has retired. The partial index serves the due query.
# The card body reuses the doc's frontmatter `summary` (already written at
# ingest), so there is no recall-generation state on this row.
CREATE_KNOWLEDGE_REVIEWS = """
CREATE TABLE IF NOT EXISTS knowledge_reviews (
    id                   BIGSERIAL PRIMARY KEY,
    doc_path             TEXT NOT NULL UNIQUE,
    captured_at          DATE NOT NULL,
    stage                INTEGER NOT NULL DEFAULT 0,
    next_due_at          DATE,                  -- NULL = retired past the final stage
    last_reviewed_at     TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS knowledge_reviews_due_idx
    ON knowledge_reviews (next_due_at)
    WHERE next_due_at IS NOT NULL;
"""

# next_signal.orchestrator.schedule state, one row per scheduled job.
# `last_slot_at` is the most recent scheduled *instant already handled*, not
# when execution happened — the two differ whenever a run was caught up or the
# scheduler was down, and comparing it against the current slot is the whole
# missed-run model. No indexes beyond the primary key: a handful of rows, only
# ever read by key or in full.
CREATE_SCHEDULE_STATE = """
CREATE TABLE IF NOT EXISTS schedule_state (
    job             TEXT PRIMARY KEY,
    last_slot_at    TIMESTAMPTZ NOT NULL,
    last_run_at     TIMESTAMPTZ,
    last_status     TEXT,                  -- 'running' | 'ok' | 'failed' | NULL (never run)
    last_error      TEXT
);
"""


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    db_name = urlparse(url).path.lstrip("/")
    if not db_name:
        print(f"could not parse db name from {url}", file=sys.stderr)
        return 2

    _ensure_database_exists(url, db_name)

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_EXTENSION)
            cur.execute(CREATE_RADAR_ITEMS)
            cur.execute(CREATE_RADAR_PUSHED_TOPICS)
            cur.execute(CREATE_RADAR_ANALYSES)
            cur.execute(CREATE_RADAR_RECAPS)
            cur.execute(CREATE_KNOWLEDGE_REVIEWS)
            cur.execute(CREATE_SCHEDULE_STATE)

        # The DDL above only creates what's missing, so a column added to an
        # existing table needs its own ALTER. Fail here rather than let the
        # gap surface later as a query error in the dashboard.
        gaps = missing_business_columns(conn)
        if gaps:
            detail = "; ".join(f"{t} missing {', '.join(c)}" for t, c in gaps.items())
            raise RuntimeError(f"schema does not satisfy the runtime contract: {detail}")

    print(f"bootstrap complete on {db_name}")
    return 0


def create_database_if_missing(admin_conn_url: str, db_name: str) -> None:
    """Connect to ``admin_conn_url`` and create ``db_name`` if it doesn't exist yet.

    Reused by scripts/container_bootstrap.sh to create the gbrain database on the
    same Postgres server without duplicating the CREATE DATABASE logic.
    """
    with psycopg.connect(admin_conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                print(f"created database {db_name}")


def _ensure_database_exists(url: str, db_name: str) -> None:
    """Connect to the default 'postgres' database and create ``db_name`` if missing."""
    parsed = urlparse(url)
    admin_url = parsed._replace(path="/postgres").geturl()
    create_database_if_missing(admin_url, db_name)


if __name__ == "__main__":
    raise SystemExit(main())
