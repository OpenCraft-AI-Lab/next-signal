"""One-time database setup: create the database (if absent), enable pgvector,
and create the custom tables that AgentOS doesn't manage for us.

agno's PostgresDb auto-provisions sessions / memory / knowledge / traces on
first use, so we don't touch those here — only the things specific to this
framework: scheduling state and per-tool persistent state.

Usage::

    DATABASE_URL=postgresql://localhost/next_signal uv run python scripts/bootstrap_db.py
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import psycopg
from psycopg import sql


CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector"

CREATE_JOB_RUNS = """
CREATE TABLE IF NOT EXISTS job_runs (
    id              BIGSERIAL PRIMARY KEY,
    job_name        TEXT NOT NULL,
    workflow_name   TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running',  -- running | success | failed
    exit_code       INTEGER,
    trace_id        TEXT,
    output          TEXT,
    error           TEXT,
    log_path        TEXT,
    inputs_json     JSONB
);
CREATE INDEX IF NOT EXISTS job_runs_job_name_idx ON job_runs (job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS job_runs_status_idx ON job_runs (status) WHERE status = 'running';
"""

CREATE_SCHEDULED_JOBS = """
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    name            TEXT PRIMARY KEY,
    workflow_name   TEXT NOT NULL,
    when_spec       JSONB NOT NULL,
    inputs_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    notify          TEXT NOT NULL DEFAULT 'none',
    enabled         BOOLEAN NOT NULL DEFAULT true,
    plist_path      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# paca.collectors.info_radar state.
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

# paca.workflows.info_radar_analysis: long-term memory of pushed topics so the
# dedup gate can detect a paraphrase of something already presented. Embedding
# dim is fixed at 1024 to match the default `Qwen3-Embedding-0.6B-8bit` embedder
# profile (see design.md §D5); swapping embedders requires a column migration.
CREATE_RADAR_PUSHED_TOPICS = """
CREATE TABLE IF NOT EXISTS radar_pushed_topics (
    id              BIGSERIAL PRIMARY KEY,
    topic_summary   TEXT NOT NULL,
    embedding       vector(1024) NOT NULL,
    item_ids        JSONB NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS radar_pushed_topics_embedding_idx
    ON radar_pushed_topics
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""

# paca.workflows.info_radar_analysis: one row per radar_items row that's been
# through the analysis pipeline. UNIQUE(radar_item_id) makes re-runs idempotent.
# ON DELETE CASCADE: when the 30-day sweep drops a radar_items row, its
# analysis row goes with it (analysis is downstream-bounded).
CREATE_RADAR_ANALYSES = """
CREATE TABLE IF NOT EXISTS radar_analyses (
    id              BIGSERIAL PRIMARY KEY,
    radar_item_id   BIGINT NOT NULL REFERENCES radar_items(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL,            -- 'drop' | 'keep'
    tier1_reason    TEXT,
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
CREATE INDEX IF NOT EXISTS radar_analyses_unpushed_idx
    ON radar_analyses (analyzed_at)
    WHERE verdict='keep' AND dedup_status='novel' AND pushed_at IS NULL;
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
            cur.execute(CREATE_JOB_RUNS)
            cur.execute(CREATE_SCHEDULED_JOBS)
            cur.execute(CREATE_RADAR_ITEMS)
            cur.execute(CREATE_RADAR_PUSHED_TOPICS)
            cur.execute(CREATE_RADAR_ANALYSES)

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
