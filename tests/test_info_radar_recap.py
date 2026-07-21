"""Tests for the info-radar recap workflow.

Store and agent calls are mocked, so these run without Postgres or OMLX. The
SQL-level gate itself (BETWEEN in the radar timezone, verdict='keep',
novel-only) is exercised by the container end-to-end check, not here — these
cover the Python-side contract: range validation, selection bounds, citation
validation, cache/lifecycle behavior, and payload shape.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from paca.workflows import info_radar_recap as recap
from paca.workflows.info_radar_recap import RecapOutput, Theme


def _item(item_id: int, score: int = 50) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": f"title-{item_id}",
        "score": score,
        "tags": ["tag"],
        "summary": f"summary-{item_id}",
    }


@pytest.fixture
def fake_store(monkeypatch):
    """Capture store calls and serve programmable responses."""
    state: dict[str, Any] = {
        "candidates": [],
        "considered": 0,
        "watermark": None,
        "cached": None,
        "claim": True,
        "select_kwargs": [],
        "finish": [],
        "fail": [],
        "begin": [],
    }

    def fake_select(**kwargs):
        state["select_kwargs"].append(kwargs)
        return list(state["candidates"]), state["considered"], state["watermark"]

    def fake_begin(**kwargs):
        state["begin"].append(kwargs)
        return state["claim"]

    monkeypatch.setattr(recap.store, "select_candidates", fake_select)
    monkeypatch.setattr(recap.store, "read_recap", lambda **kw: state["cached"])
    monkeypatch.setattr(recap.store, "begin_recap", fake_begin)
    monkeypatch.setattr(recap.store, "finish_recap", lambda **kw: state["finish"].append(kw))
    monkeypatch.setattr(recap.store, "fail_recap", lambda **kw: state["fail"].append(kw))
    monkeypatch.setattr(recap.store, "today_local", lambda: date(2026, 7, 20))
    return state


def _stub_generate(monkeypatch, output: RecapOutput):
    monkeypatch.setattr(recap, "_generate", lambda *a, **kw: output)


# --- range validation -------------------------------------------------------


def test_inverted_range_raises(fake_store):
    with pytest.raises(RuntimeError, match="precedes since"):
        recap.run(since="2026-07-19", until="2026-07-13")
    assert fake_store["select_kwargs"] == []


def test_unparseable_date_raises(fake_store):
    with pytest.raises(RuntimeError, match="not a YYYY-MM-DD date"):
        recap.run(since="last tuesday", until="2026-07-19")


def test_range_defaults_to_trailing_seven_days(fake_store, monkeypatch):
    _stub_generate(monkeypatch, RecapOutput(headline="h", themes=[]))
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1
    recap.run()
    kwargs = fake_store["select_kwargs"][0]
    # Inclusive 7-day window ending on the radar-timezone today.
    assert kwargs["since"] == date(2026, 7, 14)
    assert kwargs["until"] == date(2026, 7, 20)


# --- selection bounds -------------------------------------------------------


def test_selection_uses_the_documented_cap(fake_store, monkeypatch):
    _stub_generate(monkeypatch, RecapOutput(headline="h", themes=[]))
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1
    recap.run(since="2026-07-13", until="2026-07-19")
    assert fake_store["select_kwargs"][0]["cap"] == recap._MAX_ITEMS == 60


def test_capped_run_records_both_counts(fake_store, monkeypatch):
    items = [_item(i) for i in range(1, 61)]
    _stub_generate(
        monkeypatch,
        RecapOutput(headline="h", themes=[Theme(title="t", narrative="n", item_ids=[1])]),
    )
    fake_store["candidates"] = items
    fake_store["considered"] = 143
    result = recap.run(since="2026-07-01", until="2026-07-31")
    assert result["item_count"] == 60
    assert result["considered_count"] == 143
    assert fake_store["finish"][0]["item_count"] == 60
    assert fake_store["finish"][0]["considered_count"] == 143


def test_uncapped_run_records_equal_counts(fake_store, monkeypatch):
    _stub_generate(
        monkeypatch,
        RecapOutput(headline="h", themes=[Theme(title="t", narrative="n", item_ids=[1])]),
    )
    fake_store["candidates"] = [_item(i) for i in range(1, 19)]
    fake_store["considered"] = 18
    result = recap.run(since="2026-07-13", until="2026-07-19")
    assert result["item_count"] == result["considered_count"] == 18


# --- citation validation ----------------------------------------------------


def test_unknown_citation_is_dropped_recap_survives():
    themes = recap._validate_themes(
        [Theme(title="a", narrative="n", item_ids=[12, 31, 9999])], {12, 31}
    )
    assert themes == [{"title": "a", "narrative": "n", "item_ids": [12, 31]}]


def test_theme_with_no_valid_citation_is_dropped():
    themes = recap._validate_themes(
        [
            Theme(title="keep", narrative="n", item_ids=[1]),
            Theme(title="drop", narrative="n", item_ids=[404]),
        ],
        {1, 2, 3},
    )
    assert [t["title"] for t in themes] == ["keep"]


def test_all_citations_invalid_is_an_error_not_an_empty_recap(fake_store, monkeypatch):
    _stub_generate(
        monkeypatch,
        RecapOutput(
            headline="h", themes=[Theme(title="t", narrative="n", item_ids=[9999])]
        ),
    )
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1
    result = recap.run(since="2026-07-13", until="2026-07-19")
    assert result["status"] == "error"
    assert fake_store["finish"] == []
    assert "no theme survived" in fake_store["fail"][0]["error"]


# --- cache and lifecycle ----------------------------------------------------


def test_cached_done_recap_skips_selection_and_generation(fake_store, monkeypatch):
    fake_store["cached"] = {
        "since": date(2026, 7, 13),
        "until": date(2026, 7, 19),
        "min_score": 0,
        "novel_only": False,
        "status": "done",
        "headline": "stored",
        "themes": [{"title": "t", "narrative": "n", "item_ids": [1]}],
        "item_count": 5,
        "considered_count": 5,
    }

    def explode(*a, **kw):
        raise AssertionError("agent must not be called for a cached recap")

    monkeypatch.setattr(recap, "_generate", explode)
    result = recap.run(since="2026-07-13", until="2026-07-19")
    assert result["status"] == "cached"
    assert result["headline"] == "stored"
    assert fake_store["select_kwargs"] == []


def test_regenerate_bypasses_the_cache(fake_store, monkeypatch):
    fake_store["cached"] = {"status": "done", "headline": "old"}
    _stub_generate(
        monkeypatch,
        RecapOutput(headline="new", themes=[Theme(title="t", narrative="n", item_ids=[1])]),
    )
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1
    result = recap.run(since="2026-07-13", until="2026-07-19", regenerate=True)
    assert result["status"] == "done"
    assert result["headline"] == "new"


def test_already_running_key_is_a_no_op(fake_store, monkeypatch):
    fake_store["claim"] = False
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1

    def explode(*a, **kw):
        raise AssertionError("agent must not be called while a run is in flight")

    monkeypatch.setattr(recap, "_generate", explode)
    result = recap.run(since="2026-07-13", until="2026-07-19")
    assert result["status"] == "running"
    assert fake_store["finish"] == []


def test_agent_failure_records_error_and_persists_nothing(fake_store, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("omlx unreachable")

    monkeypatch.setattr(recap, "_generate", boom)
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1
    result = recap.run(since="2026-07-13", until="2026-07-19")
    assert result["status"] == "error"
    assert fake_store["finish"] == []
    assert fake_store["fail"][0]["error"] == "omlx unreachable"


# --- empty range ------------------------------------------------------------


def test_empty_range_makes_no_agent_call_and_writes_no_row(fake_store, monkeypatch):
    def explode(*a, **kw):
        raise AssertionError("agent must not be called for an empty range")

    monkeypatch.setattr(recap, "_generate", explode)
    result = recap.run(since="2026-07-13", until="2026-07-19")
    assert result["status"] == "empty"
    assert result["considered_count"] == 0
    assert fake_store["begin"] == []
    assert fake_store["finish"] == []
    assert fake_store["fail"] == []


# --- payload shape ----------------------------------------------------------


def test_payload_carries_summaries_and_never_impact_md(fake_store, monkeypatch):
    captured: dict[str, Any] = {}

    class _DummyAgent:
        name = "radar_recap"

    monkeypatch.setattr(
        "paca.agents.loader.build_from_name", lambda name: _DummyAgent()
    )

    def fake_run_structured(agent, agent_input, schema, **kw):  # noqa: ARG001
        captured["input"] = agent_input
        return RecapOutput(
            headline="h", themes=[Theme(title="t", narrative="n", item_ids=[1])]
        )

    monkeypatch.setattr("paca.agents.structured.run_structured", fake_run_structured)
    fake_store["candidates"] = [_item(1)]
    fake_store["considered"] = 1
    recap.run(since="2026-07-13", until="2026-07-19")

    payload = json.loads(captured["input"])
    assert payload["since"] == "2026-07-13"
    assert payload["until"] == "2026-07-19"
    assert set(payload["items"][0]) == {"id", "title", "score", "tags", "summary"}
    assert "impact_md" not in captured["input"]
