"""Store tests against a real Postgres. Skipped if DATABASE_URL is not set.

Uses a unique source-name prefix per test so concurrent runs don't collide,
and cleans up after itself. We do NOT create a separate schema — re-uses the
project DB so the DDL in scripts/bootstrap_db.py is the source of truth.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("psycopg")
import psycopg  # noqa: E402

from paca.collectors.info_radar import store  # noqa: E402
from paca.collectors.info_radar.schema import RadarItem  # noqa: E402


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; skipping info-radar store integration tests",
)


def _has_table(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM radar_items LIMIT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


if DATABASE_URL and not _has_table(DATABASE_URL):
    pytest.skip(
        "radar_items table missing; run `uv run python scripts/bootstrap_db.py`",
        allow_module_level=True,
    )


@pytest.fixture
def source_name():
    """Unique per-test source name so dedup state doesn't leak."""
    name = f"test_radar_{uuid.uuid4().hex[:12]}"
    yield name
    # Cleanup
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM radar_items WHERE source = %s", (name,))
        conn.commit()


def _item(source_id: str, **overrides) -> RadarItem:
    return RadarItem(
        source_id=source_id,
        title=overrides.get("title", f"title-{source_id}"),
        url=overrides.get("url", f"https://example.com/{source_id}"),
        excerpt=overrides.get("excerpt", "x"),
        published_at=overrides.get("published_at", datetime(2026, 5, 25, tzinfo=timezone.utc)),
        payload=overrides.get("payload", {"id": source_id}),
    )


def test_upsert_writes_new_items(source_name) -> None:
    written, skipped = store.upsert_items(source_name, [_item("a"), _item("b")])
    assert (written, skipped) == (2, 0)


def test_reupsert_skips_duplicates(source_name) -> None:
    store.upsert_items(source_name, [_item("a"), _item("b")])
    written, skipped = store.upsert_items(source_name, [_item("a"), _item("b"), _item("c")])
    assert (written, skipped) == (1, 2)


def test_query_recent_returns_within_window(source_name) -> None:
    store.upsert_items(source_name, [_item("a"), _item("b")])
    rows = store.query_recent(source=source_name, limit=10)
    assert {r["source_id"] for r in rows} == {"a", "b"}


def test_sweep_removes_expired_rows(source_name) -> None:
    store.upsert_items(source_name, [_item("fresh")])
    # Backdate one row past 30 days.
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO radar_items
                    (source, source_id, title, payload, fetched_at)
                VALUES (%s, %s, %s, %s::jsonb, now() - interval '31 days')
                """,
                (source_name, "stale", "stale-title", "{}"),
            )
        conn.commit()

    # query_recent already filters by window — stale shouldn't appear.
    pre = {r["source_id"] for r in store.query_recent(source=source_name, limit=10)}
    assert pre == {"fresh"}

    deleted = store.sweep_expired()
    assert deleted >= 1  # at least our backdated row

    # And the table no longer has the stale row.
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM radar_items WHERE source = %s AND source_id = %s",
                (source_name, "stale"),
            )
            (count,) = cur.fetchone()
    assert count == 0
