"""knowledge_reviews store tests against a real Postgres. Skipped without DATABASE_URL.

Uses a unique doc_path prefix per test so concurrent runs don't collide, and
cleans up after itself. Re-uses the project DB so the DDL in
scripts/bootstrap_db.py is the source of truth. Covers enroll / unenroll and the
due predicate (`next_due_at <= today` in the radar tz, retirement excluded).
Due ordering and the "seen" advance live in the dashboard's SQL.
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta

import pytest

pytest.importorskip("psycopg")
import psycopg  # noqa: E402

from paca.workflows.knowledge_review import store  # noqa: E402


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set; skipping knowledge-review store integration tests",
)


def _has_table(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM knowledge_reviews LIMIT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


if DATABASE_URL and not _has_table(DATABASE_URL):
    pytest.skip(
        "knowledge_reviews table missing; run `uv run python scripts/bootstrap_db.py`",
        allow_module_level=True,
    )


@pytest.fixture
def prefix():
    """Unique per-test doc_path prefix so rows don't leak between tests."""
    p = f"test-review-{uuid.uuid4().hex[:12]}/"
    yield p
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_reviews WHERE doc_path LIKE %s", (p + "%",))
        conn.commit()


def _seed(prefix, name, *, next_due, stage=0):
    store.insert_seeded(
        [
            {
                "doc_path": prefix + name,
                "captured_at": store.today_local(),
                "stage": stage,
                "next_due_at": next_due,
            }
        ]
    )


def test_insert_and_existing_round_trip(prefix):
    _seed(prefix, "a.md", next_due=store.today_local())
    _seed(prefix, "b.md", next_due=store.today_local())
    existing = store.existing_doc_paths()
    assert {prefix + "a.md", prefix + "b.md"} <= existing


def test_insert_is_idempotent_on_conflict(prefix):
    today = store.today_local()
    row = [{"doc_path": prefix + "a.md", "captured_at": today, "stage": 0, "next_due_at": today}]
    assert store.insert_seeded(row) == 1
    assert store.insert_seeded(row) == 0  # ON CONFLICT DO NOTHING


def test_count_due_counts_only_due_today(prefix):
    before = store.count_due()
    today = store.today_local()
    _seed(prefix, "due.md", next_due=today)
    _seed(prefix, "overdue.md", next_due=today - timedelta(days=3))
    _seed(prefix, "future.md", next_due=today + timedelta(days=1))
    _seed(prefix, "retired.md", next_due=None, stage=7)
    # Only the two <= today, non-NULL rows count; future and retired are excluded.
    assert store.count_due() - before == 2


def test_delete_paths_unenrolls(prefix):
    _seed(prefix, "gone.md", next_due=store.today_local())
    assert store.delete_paths([prefix + "gone.md"]) == 1
    assert prefix + "gone.md" not in store.existing_doc_paths()
