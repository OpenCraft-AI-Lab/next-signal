"""Store tests against a real Postgres. Skipped if DATABASE_URL is not set
or if the radar_analyses / radar_pushed_topics tables are missing.

Mirrors tests/test_info_radar_store.py: per-test source prefix, cleanup at
teardown, never creates a separate schema.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("psycopg")
import psycopg  # noqa: E402

from paca.collectors.info_radar import store as collector_store  # noqa: E402
from paca.collectors.info_radar.schema import RadarItem  # noqa: E402
from paca.workflows.info_radar_analysis import store as analysis_store  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; skipping analysis-store integration tests",
)


def _has_tables(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM radar_analyses LIMIT 1")
                cur.fetchone()
                cur.execute("SELECT 1 FROM radar_pushed_topics LIMIT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


if DATABASE_URL and not _has_tables(DATABASE_URL):
    pytest.skip(
        "radar_analyses / radar_pushed_topics tables missing; "
        "run `uv run python scripts/bootstrap_db.py`",
        allow_module_level=True,
    )


@pytest.fixture
def source_name():
    """Per-test source prefix so we can clean up our own rows."""
    name = f"test_radar_analysis_{uuid.uuid4().hex[:12]}"
    yield name
    # Cleanup. radar_analyses cascades from radar_items; pushed_topics rows
    # we created with this source's items get cleaned by scanning item_ids.
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Collect the radar_items ids we used so we can purge associated
            # pushed_topics rows even though there's no FK.
            cur.execute("SELECT id FROM radar_items WHERE source = %s", (name,))
            our_ids = {r[0] for r in cur.fetchall()}
            if our_ids:
                # Best-effort topic cleanup: drop any topic whose item_ids list
                # is a subset of our ids.
                cur.execute(
                    "SELECT id, item_ids FROM radar_pushed_topics WHERE "
                    "(SELECT bool_and((value::text)::bigint = ANY(%s::bigint[])) "
                    " FROM jsonb_array_elements(item_ids))",
                    (list(our_ids),),
                )
                topic_ids = [r[0] for r in cur.fetchall()]
                if topic_ids:
                    cur.execute(
                        "DELETE FROM radar_pushed_topics WHERE id = ANY(%s)",
                        (topic_ids,),
                    )
            cur.execute("DELETE FROM radar_items WHERE source = %s", (name,))
        conn.commit()


def _seed_item(source: str, sid: str) -> int:
    """Insert one radar_items row, return its id."""
    item = RadarItem(
        source_id=sid,
        title=f"title-{sid}",
        url=f"https://example.com/{sid}",
        excerpt="x",
        published_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
        payload={"id": sid},
    )
    collector_store.upsert_items(source, [item])
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM radar_items WHERE source = %s AND source_id = %s",
                (source, sid),
            )
            (row_id,) = cur.fetchone()
    return int(row_id)


def test_fetch_unseen_returns_only_unseen(source_name) -> None:
    a = _seed_item(source_name, "a")
    _seed_item(source_name, "b")
    # Mark a as seen via the analysis layer.
    analysis_store.mark_seen(a)

    rows = analysis_store.fetch_unseen_items(source=source_name, limit=10)
    ids = {r["id"] for r in rows}
    assert a not in ids
    assert any(r["source_id"] == "b" for r in rows)


def test_insert_analysis_is_idempotent(source_name) -> None:
    item_id = _seed_item(source_name, "i1")

    first = analysis_store.insert_analysis(
        radar_item_id=item_id, verdict="drop", tier1_reason="noise"
    )
    second = analysis_store.insert_analysis(
        radar_item_id=item_id, verdict="drop", tier1_reason="should be ignored"
    )
    assert isinstance(first, int) and first > 0
    assert second is None  # ON CONFLICT DO NOTHING


def test_mark_seen_sets_timestamp(source_name) -> None:
    item_id = _seed_item(source_name, "s1")
    analysis_store.mark_seen(item_id)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT seen_at FROM radar_items WHERE id = %s", (item_id,))
            (seen_at,) = cur.fetchone()
    assert seen_at is not None


def test_topic_lifecycle_and_ann_search(source_name) -> None:
    item_a = _seed_item(source_name, "ta")
    item_b = _seed_item(source_name, "tb")

    # Use deterministic, very different unit-ish vectors.
    close_to_a = [1.0] + [0.0] * 1023
    far_from_a = [0.0] * 512 + [1.0] + [0.0] * 511

    topic_id = analysis_store.insert_topic(
        summary="topic-A summary", embedding=close_to_a, item_id=item_a
    )
    assert topic_id > 0

    # ANN search with a vector close to topic-A should find it.
    hits = analysis_store.ann_search_topics(close_to_a, k=5, threshold=0.40)
    found = [h for h in hits if h["id"] == topic_id]
    assert found, f"expected topic {topic_id} in {hits}"
    assert found[0]["distance"] < 0.1

    # ANN search with a far vector should not return our topic under the
    # threshold (cosine distance to orthogonal ≈ 1.0).
    hits_far = analysis_store.ann_search_topics(far_from_a, k=5, threshold=0.40)
    assert all(h["id"] != topic_id for h in hits_far)

    # Append item_b to the same topic.
    analysis_store.append_item_to_topic(topic_id=topic_id, item_id=item_b)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT item_ids FROM radar_pushed_topics WHERE id = %s",
                (topic_id,),
            )
            (item_ids,) = cur.fetchone()
    assert sorted(int(x) for x in item_ids) == sorted([item_a, item_b])
