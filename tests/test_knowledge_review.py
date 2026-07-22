"""Tests for the knowledge-review scheduling core.

Store calls are monkeypatched, so these run without Postgres. The SQL itself
(due ordering, timezone day boundary, retirement exclusion) is covered by
tests/test_knowledge_review_store.py against a real database and by the
container end-to-end check. Here we cover the Python-side contract: the curve
arithmetic and reconciliation diffing plus the empty-wiki guard.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from paca.workflows import knowledge_review as kr


# --- curve arithmetic (tasks 8.1, 8.2, 8.3) ---------------------------------

TODAY = date(2026, 7, 21)


def test_fresh_doc_is_due_tomorrow_not_today():
    stage, next_due = kr.schedule_seed(TODAY, TODAY)
    assert stage == 0
    assert next_due == TODAY + timedelta(days=1)


def test_old_doc_seeds_near_the_end_of_the_curve():
    # Captured 100 days ago: offsets 1..60 have elapsed, 120 has not.
    stage, next_due = kr.schedule_seed(TODAY - timedelta(days=100), TODAY)
    assert kr.STAGES[stage] == 120
    assert next_due == (TODAY - timedelta(days=100)) + timedelta(days=120)
    assert next_due > TODAY  # 20 days in the future, no overdue reviews


def test_very_old_doc_seeds_retired():
    stage, next_due = kr.schedule_seed(TODAY - timedelta(days=200), TODAY)
    assert stage == len(kr.STAGES)
    assert next_due is None


def test_late_review_fast_forwards_without_cascading():
    # A 15-day-stage card (index 3) marked seen on day 40: naive stage+1 would be
    # index 4 (day 30), already overdue. Fast-forward jumps past every elapsed
    # stage to index 5 (day 60), which is in the future.
    captured = TODAY - timedelta(days=40)
    stage, next_due = kr.schedule_advance(3, captured, TODAY)
    assert stage == 5
    assert next_due is not None and next_due > TODAY


def test_advancing_past_final_stage_retires():
    captured = TODAY - timedelta(days=200)
    stage, next_due = kr.schedule_advance(len(kr.STAGES) - 1, captured, TODAY)
    assert stage >= len(kr.STAGES)
    assert next_due is None


def test_seed_and_advance_never_schedule_in_the_past():
    # Sweep a year of capture ages against a range of prior stages; the assert
    # inside _due_checked would fire if any path produced a past-due date.
    for age in range(0, 365, 7):
        captured = TODAY - timedelta(days=age)
        _, seed_due = kr.schedule_seed(captured, TODAY)
        assert seed_due is None or seed_due > TODAY
        for stage in range(len(kr.STAGES)):
            _, adv_due = kr.schedule_advance(stage, captured, TODAY)
            assert adv_due is None or adv_due > TODAY


# --- reconciliation (task 8.4) ----------------------------------------------


@pytest.fixture
def wiki(tmp_path, monkeypatch):
    """A wiki root with helpers to add docs and observe store writes."""
    monkeypatch.setenv("PACA_WIKI_DIR", str(tmp_path))
    monkeypatch.setattr(kr.store, "today_local", lambda: TODAY)

    calls: dict[str, Any] = {"seeded": None, "deleted": None, "existing": set()}

    def fake_insert(rows):
        calls["seeded"] = rows
        return len(rows)

    def fake_delete(paths):
        calls["deleted"] = paths
        return len(paths)

    monkeypatch.setattr(kr.store, "existing_doc_paths", lambda: set(calls["existing"]))
    monkeypatch.setattr(kr.store, "insert_seeded", fake_insert)
    monkeypatch.setattr(kr.store, "delete_paths", fake_delete)

    def add(rel: str, captured: str | None = None):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        front = f"---\ncaptured_at: {captured}\n---\n" if captured else ""
        p.write_text(f"{front}# {rel}\nbody\n", encoding="utf-8")

    return type("Wiki", (), {"root": tmp_path, "add": staticmethod(add), "calls": calls})


def test_sync_enrolls_only_unknown_docs(wiki):
    wiki.add("a.md")
    wiki.add("sub/b.md")
    wiki.add("c.md")
    wiki.calls["existing"] = {"a.md"}

    enrolled, unenrolled = kr.sync()

    seeded_paths = {r["doc_path"] for r in wiki.calls["seeded"]}
    assert seeded_paths == {"sub/b.md", "c.md"}
    assert enrolled == 2
    assert unenrolled == 0
    assert wiki.calls["deleted"] == []


def test_sync_is_idempotent(wiki):
    wiki.add("a.md")
    wiki.add("b.md")
    wiki.calls["existing"] = {"a.md", "b.md"}

    enrolled, unenrolled = kr.sync()

    assert wiki.calls["seeded"] == []
    assert wiki.calls["deleted"] == []
    assert (enrolled, unenrolled) == (0, 0)


def test_sync_unenrolls_deleted_docs(wiki):
    wiki.add("a.md")
    wiki.add("b.md")
    wiki.calls["existing"] = {"a.md", "b.md", "gone.md"}

    enrolled, unenrolled = kr.sync()

    assert wiki.calls["seeded"] == []
    assert wiki.calls["deleted"] == ["gone.md"]
    assert (enrolled, unenrolled) == (0, 1)


def test_sync_seeds_with_frontmatter_capture_date(wiki):
    wiki.add("old.md", captured=str(TODAY - timedelta(days=100)))
    wiki.calls["existing"] = set()

    kr.sync()

    row = wiki.calls["seeded"][0]
    assert row["captured_at"] == TODAY - timedelta(days=100)
    assert kr.STAGES[row["stage"]] == 120


def test_empty_wiki_raises_without_deleting(wiki):
    # Root exists (created by tmp_path) but holds no markdown docs.
    wiki.calls["existing"] = {"a.md", "b.md"}

    with pytest.raises(RuntimeError, match="no markdown docs"):
        kr.sync()

    assert wiki.calls["deleted"] is None  # nothing was unenrolled


def test_missing_wiki_root_raises_without_deleting(tmp_path, monkeypatch):
    monkeypatch.setenv("PACA_WIKI_DIR", str(tmp_path / "does-not-exist"))
    deleted: list[Any] = []
    monkeypatch.setattr(kr.store, "existing_doc_paths", lambda: {"a.md"})
    monkeypatch.setattr(kr.store, "delete_paths", lambda p: deleted.append(p))
    monkeypatch.setattr(kr.store, "insert_seeded", lambda rows: len(rows))

    with pytest.raises(RuntimeError):
        kr.sync()

    assert deleted == []
