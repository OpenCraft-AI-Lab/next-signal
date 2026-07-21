"""Runner tests for info-radar-analysis. All store + agent calls are mocked,
so these tests do not require a real Postgres or OMLX.

Covers both the batched tier-1 happy path and the per-chunk fallback to
size-1 calls when a batch fails its validation (length / index mismatch).
"""

from __future__ import annotations

from typing import Any

import pytest

from paca.workflows.info_radar_analysis import runner
from paca.workflows.info_radar_analysis.goals import Goal
from paca.workflows.info_radar_analysis.schemas import (
    Tier1Verdict,
    Tier2Analysis,
)
from paca.workflows.info_radar_analysis.stages import dedup as dedup_mod


_GOAL = Goal(
    name="g",
    description="any",
    topics=["topic"],
    keywords=["kw"],
)


def _item(item_id: int, *, source: str = "src", source_id: str = "sid") -> dict[str, Any]:
    return {
        "id": item_id,
        "source": source,
        "source_id": source_id,
        "title": f"title-{item_id}",
        "url": f"https://example.com/{item_id}",
        "excerpt": f"excerpt-{item_id}",
        "payload": {},
    }


@pytest.fixture
def fake_store(monkeypatch):
    """Capture all analysis_store calls and serve programmable responses."""
    insert_calls: list[dict] = []
    mark_seen_calls: list[int] = []
    topic_calls: list[dict] = []
    append_calls: list[dict] = []
    ann_response: list[dict] = []  # mutated by tests
    item_queue: list[dict] = []

    def fake_fetch(*, limit=None, source=None):  # noqa: ARG001
        return list(item_queue)

    def fake_insert(**kwargs):
        insert_calls.append(kwargs)
        return len(insert_calls)

    def fake_mark_seen(item_id):
        mark_seen_calls.append(int(item_id))

    def fake_insert_topic(*, summary, embedding, item_id):  # noqa: ARG001
        topic_calls.append({"summary": summary, "item_id": item_id})
        return 100 + len(topic_calls)

    def fake_append(*, topic_id, item_id):
        append_calls.append({"topic_id": topic_id, "item_id": item_id})

    def fake_ann(embedding, *, k=5, threshold=0.40):  # noqa: ARG001
        return list(ann_response)

    monkeypatch.setattr(runner.analysis_store, "fetch_unseen_items", fake_fetch)
    monkeypatch.setattr(runner.analysis_store, "insert_analysis", fake_insert)
    monkeypatch.setattr(runner.analysis_store, "mark_seen", fake_mark_seen)
    monkeypatch.setattr(runner.analysis_store, "insert_topic", fake_insert_topic)
    monkeypatch.setattr(runner.analysis_store, "append_item_to_topic", fake_append)
    # dedup stage looks up store via its own import alias
    monkeypatch.setattr(dedup_mod.analysis_store, "ann_search_topics", fake_ann)

    monkeypatch.setattr(runner, "load_goals", lambda: [_GOAL])

    return {
        "queue": item_queue,
        "insert_calls": insert_calls,
        "mark_seen_calls": mark_seen_calls,
        "topic_calls": topic_calls,
        "append_calls": append_calls,
        "ann_response": ann_response,
    }


@pytest.fixture
def fake_stages(monkeypatch):
    """Programmable per-item / per-batch responses for the four stages.

    Tier-1 has TWO entry points to patch:
      * ``tier1.run_batch`` — called per chunk by the runner
      * ``tier1.run``       — called only by the per-item fallback path

    Tests can set ``batch_results[<frozenset(item_ids)>]`` to either a
    ``list[Tier1Verdict]`` (success) or an exception (forces fallback).
    Per-item fallback responses go in ``tier1_results[item_id]``.
    """
    batch_results: dict[frozenset, object] = {}
    tier1_results: dict[int, object] = {}
    fetch_results: dict[int, object] = {}
    tier2_results: dict[int, object] = {}
    dedup_results: dict[int, object] = {}

    def fake_run_batch(items, goals, locale="zh"):  # noqa: ARG001
        key = frozenset(int(i["id"]) for i in items)
        if key not in batch_results:
            # Default: succeed with whatever per-item answers are configured,
            # or raise so the test sees an obvious missing-setup.
            verdicts = []
            for item in items:
                r = tier1_results.get(int(item["id"]))
                if r is None or isinstance(r, Exception):
                    raise AssertionError(
                        f"no batch_results or tier1_results entry for items={key}"
                    )
                verdicts.append(r)
            return verdicts
        r = batch_results[key]
        if isinstance(r, Exception):
            raise r
        return list(r)

    def fake_tier1(item, goals, locale="zh"):  # noqa: ARG001
        r = tier1_results[int(item["id"])]
        if isinstance(r, Exception):
            raise r
        return r

    def fake_fetch(item):
        r = fetch_results[int(item["id"])]
        if isinstance(r, Exception):
            raise r
        return r

    def fake_tier2(item, content, status, goals, locale="zh"):  # noqa: ARG001
        r = tier2_results[int(item["id"])]
        if isinstance(r, Exception):
            raise r
        return r

    def fake_dedup(summary, locale="zh", **_):  # noqa: ARG001
        r = dedup_results.pop("next")
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(runner.tier1, "run_batch", fake_run_batch)
    monkeypatch.setattr(runner.tier1, "run", fake_tier1)
    monkeypatch.setattr(runner.fetch, "run", fake_fetch)
    monkeypatch.setattr(runner.tier2, "run", fake_tier2)
    monkeypatch.setattr(runner.dedup, "run", fake_dedup)

    return {
        "batch": batch_results,
        "tier1": tier1_results,
        "fetch": fetch_results,
        "tier2": tier2_results,
        "dedup": dedup_results,
    }


# ---------------------------------------------------------------------------
# Existing per-item semantics — all still pass through batched tier-1
# ---------------------------------------------------------------------------


def test_no_unseen_items_returns_zero_counters(fake_store, fake_stages) -> None:
    result = runner.run()
    assert result["items_total"] == 0
    assert result["tier1_kept"] == 0
    assert fake_store["insert_calls"] == []
    assert fake_store["mark_seen_calls"] == []


def test_tier1_drop_marks_seen_and_persists(fake_store, fake_stages) -> None:
    fake_store["queue"].append(_item(1))
    fake_stages["batch"][frozenset({1})] = [
        Tier1Verdict(verdict="drop", reason="off-topic")
    ]

    result = runner.run()

    assert result["tier1_dropped"] == 1
    assert result["tier1_kept"] == 0
    assert fake_store["mark_seen_calls"] == [1]
    assert len(fake_store["insert_calls"]) == 1
    call = fake_store["insert_calls"][0]
    assert call["verdict"] == "drop"
    assert call["tier1_reason"] == "off-topic"


def test_tier2_keep_novel_inserts_topic(fake_store, fake_stages) -> None:
    fake_store["queue"].append(_item(2))
    fake_stages["batch"][frozenset({2})] = [Tier1Verdict(verdict="keep", reason="matches")]
    fake_stages["fetch"][2] = ("full body", "full")
    fake_stages["tier2"][2] = Tier2Analysis(
        summary="s", impact="i", score=80, tags=["release"]
    )
    fake_stages["dedup"]["next"] = dedup_mod.DedupOutcome(
        status="novel", matched_topic_id=None, embedding=[0.1] * 1024
    )

    result = runner.run()

    assert result["tier1_kept"] == 1
    assert result["tier2_ok"] == 1
    assert result["dedup_novel"] == 1
    assert len(fake_store["topic_calls"]) == 1
    assert fake_store["topic_calls"][0]["item_id"] == 2
    assert fake_store["mark_seen_calls"] == [2]
    call = fake_store["insert_calls"][0]
    assert call["verdict"] == "keep"
    assert call["dedup_status"] == "novel"
    assert call["dedup_match_id"] == 101


def test_tier2_keep_duplicate_appends_to_topic(fake_store, fake_stages) -> None:
    fake_store["queue"].append(_item(3))
    fake_stages["batch"][frozenset({3})] = [Tier1Verdict(verdict="keep", reason="ok")]
    fake_stages["fetch"][3] = ("body", "full")
    fake_stages["tier2"][3] = Tier2Analysis(summary="s", impact="i", score=50, tags=[])
    fake_stages["dedup"]["next"] = dedup_mod.DedupOutcome(
        status="duplicate", matched_topic_id=42, embedding=[0.0] * 1024
    )

    result = runner.run()

    assert result["dedup_duplicate"] == 1
    assert fake_store["append_calls"] == [{"topic_id": 42, "item_id": 3}]
    assert fake_store["topic_calls"] == []
    call = fake_store["insert_calls"][0]
    assert call["dedup_status"] == "duplicate"
    assert call["dedup_match_id"] == 42


def test_tier2_error_is_isolated_and_retries_next_run(fake_store, fake_stages) -> None:
    """Tier-2 failure must stay isolated AND leave the item unseen — symmetric
    with tier-1 — so a transient LLM failure retries next batch instead of
    freezing an empty analysis row forever (radar_analyses is UNIQUE per item)."""
    fake_store["queue"].extend([_item(4), _item(5)])
    fake_stages["batch"][frozenset({4, 5})] = [
        Tier1Verdict(verdict="keep", reason="r"),
        Tier1Verdict(verdict="keep", reason="r"),
    ]
    fake_stages["fetch"][4] = ("body", "full")
    fake_stages["tier2"][4] = RuntimeError("LLM blew up")
    fake_stages["fetch"][5] = ("body", "full")
    fake_stages["tier2"][5] = Tier2Analysis(summary="s", impact="i", score=70, tags=[])
    fake_stages["dedup"]["next"] = dedup_mod.DedupOutcome(
        status="novel", matched_topic_id=None, embedding=[0.0] * 1024
    )

    result = runner.run()

    assert result["tier2_error"] == 1
    assert result["tier2_ok"] == 1
    # Failed item: nothing persisted, not marked seen — retried next run.
    assert 4 not in fake_store["mark_seen_calls"]
    assert all(c["radar_item_id"] != 4 for c in fake_store["insert_calls"])
    # The healthy neighbor still completed fully.
    assert 5 in fake_store["mark_seen_calls"]


def test_fetch_fallback_flows_through_tier2(fake_store, fake_stages) -> None:
    fake_store["queue"].append(_item(6))
    fake_stages["batch"][frozenset({6})] = [Tier1Verdict(verdict="keep", reason="r")]
    fake_stages["fetch"][6] = ("description-only body", "fallback")
    fake_stages["tier2"][6] = Tier2Analysis(summary="s", impact="i", score=30, tags=[])
    fake_stages["dedup"]["next"] = dedup_mod.DedupOutcome(
        status="novel", matched_topic_id=None, embedding=[0.0] * 1024
    )

    result = runner.run()

    assert result["tier2_fallback"] == 1
    assert result["tier2_ok"] == 0
    call = fake_store["insert_calls"][0]
    assert call["content_status"] == "fallback"


def test_tier1_failure_does_not_mark_seen(fake_store, fake_stages) -> None:
    """When BOTH the batch call AND the per-item fallback fail, tier1 is
    counted as error and seen_at stays untouched."""
    fake_store["queue"].append(_item(7))
    fake_stages["batch"][frozenset({7})] = RuntimeError("batch boom")
    fake_stages["tier1"][7] = RuntimeError("single boom too")

    result = runner.run()

    assert result["tier1_error"] == 1
    assert fake_store["mark_seen_calls"] == []
    assert fake_store["insert_calls"] == []


# ---------------------------------------------------------------------------
# Batch-specific cases
# ---------------------------------------------------------------------------


def test_tier1_batch_processes_all_items_in_one_call(fake_store, fake_stages) -> None:
    """Three items in one chunk → one batch call returns three verdicts."""
    fake_store["queue"].extend([_item(10), _item(11), _item(12)])
    fake_stages["batch"][frozenset({10, 11, 12})] = [
        Tier1Verdict(verdict="drop", reason="r10"),
        Tier1Verdict(verdict="drop", reason="r11"),
        Tier1Verdict(verdict="drop", reason="r12"),
    ]

    result = runner.run()

    assert result["tier1_dropped"] == 3
    assert sorted(fake_store["mark_seen_calls"]) == [10, 11, 12]
    # One insert per item.
    assert len(fake_store["insert_calls"]) == 3


def test_tier1_batch_failure_falls_back_to_per_item(fake_store, fake_stages) -> None:
    """Batch call raises → runner retries each item alone via tier1.run."""
    fake_store["queue"].extend([_item(20), _item(21)])
    fake_stages["batch"][frozenset({20, 21})] = RuntimeError("batch validation failed")
    fake_stages["tier1"][20] = Tier1Verdict(verdict="drop", reason="single-20")
    fake_stages["tier1"][21] = Tier1Verdict(verdict="drop", reason="single-21")

    result = runner.run()

    assert result["tier1_dropped"] == 2
    reasons = {c["tier1_reason"] for c in fake_store["insert_calls"]}
    assert reasons == {"single-20", "single-21"}


def test_tier1_batch_split_across_chunks(fake_store, fake_stages, monkeypatch) -> None:
    """Items beyond _BATCH_SIZE are split into multiple batch calls."""
    monkeypatch.setattr(runner, "_BATCH_SIZE", 2)  # tiny batch for the test
    fake_store["queue"].extend([_item(30), _item(31), _item(32)])
    fake_stages["batch"][frozenset({30, 31})] = [
        Tier1Verdict(verdict="drop", reason="c1-a"),
        Tier1Verdict(verdict="drop", reason="c1-b"),
    ]
    fake_stages["batch"][frozenset({32})] = [
        Tier1Verdict(verdict="drop", reason="c2-a"),
    ]

    result = runner.run()

    assert result["tier1_dropped"] == 3
    assert sorted(fake_store["mark_seen_calls"]) == [30, 31, 32]


def test_db_error_during_persist_isolated_as_item_error(
    fake_store, fake_stages, monkeypatch
) -> None:
    """An unexpected raise (e.g. DB error in insert_analysis) for one item
    must not abort the batch — bumps `item_error` and continues."""
    fake_store["queue"].extend([_item(50), _item(51)])
    fake_stages["batch"][frozenset({50, 51})] = [
        Tier1Verdict(verdict="drop", reason="r50"),
        Tier1Verdict(verdict="drop", reason="r51"),
    ]

    real_insert = runner.analysis_store.insert_analysis
    call_seq: list[int] = []

    def flaky_insert(**kwargs):
        call_seq.append(int(kwargs["radar_item_id"]))
        if int(kwargs["radar_item_id"]) == 50:
            raise RuntimeError("Postgres connection reset")
        return real_insert(**kwargs)

    monkeypatch.setattr(runner.analysis_store, "insert_analysis", flaky_insert)

    result = runner.run()

    assert result["item_error"] == 1
    # The second item still got fully processed
    assert result["tier1_dropped"] == 1
    assert 51 in fake_store["mark_seen_calls"]
    assert 50 not in fake_store["mark_seen_calls"]
    # Both insert attempts happened (not just the failing one then abort)
    assert call_seq == [50, 51]


def test_producer_crash_does_not_hang_and_leaves_items_unseen(
    fake_store, fake_stages, monkeypatch
) -> None:
    """An unexpected raise in the producer thread (outside _run_chunk's own
    catches) must end the run cleanly: no hang, no mark_seen, items retry."""
    fake_store["queue"].extend([_item(60), _item(61)])

    def _boom(chunk, goals):  # noqa: ARG001
        raise MemoryError("producer blew up")

    monkeypatch.setattr(runner, "_run_chunk", _boom)

    result = runner.run()

    assert result["items_total"] == 2
    assert fake_store["mark_seen_calls"] == []
    assert fake_store["insert_calls"] == []


def test_tier1_partial_fallback_failure_marks_only_failures_as_error(
    fake_store, fake_stages
) -> None:
    """Batch fails; fallback succeeds for one item, fails for another."""
    fake_store["queue"].extend([_item(40), _item(41)])
    fake_stages["batch"][frozenset({40, 41})] = RuntimeError("batch boom")
    fake_stages["tier1"][40] = Tier1Verdict(verdict="drop", reason="single-ok")
    fake_stages["tier1"][41] = RuntimeError("single also failed")

    result = runner.run()

    assert result["tier1_dropped"] == 1
    assert result["tier1_error"] == 1
    # 40 dropped → mark_seen; 41 error → no mark_seen
    assert fake_store["mark_seen_calls"] == [40]
