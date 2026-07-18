"""Tests for the tier-1 batched stage.

These tests stub ``run_structured`` so they don't need a real OMLX. They
verify the validation layer that catches model misbehavior: wrong count,
wrong indices, single-item wrapper.
"""

from __future__ import annotations

import pytest

from paca.workflows.info_radar_analysis.goals import Goal
from paca.workflows.info_radar_analysis.schemas import (
    Tier1Batch,
    Tier1Decision,
)
from paca.workflows.info_radar_analysis.stages import tier1


_GOALS = [Goal(name="g", description="x", topics=[], keywords=[])]


def _item(item_id: int) -> dict:
    return {
        "id": item_id,
        "title": f"t-{item_id}",
        "excerpt": f"d-{item_id}",
        "payload": {},
    }


def _stub_run_structured(monkeypatch, response):
    """Replace ``run_structured`` so we don't touch the real agent."""
    def fake(agent, agent_input, schema, *, max_repairs=1):  # noqa: ARG001
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(tier1, "run_structured", fake)


def _stub_agent(monkeypatch) -> None:
    monkeypatch.setattr(tier1, "build_from_name", lambda name: object())


def test_run_batch_returns_verdicts_in_input_order(monkeypatch) -> None:
    _stub_agent(monkeypatch)
    # Agent returns decisions in reverse order — runner must re-sort by index.
    response = Tier1Batch(
        decisions=[
            Tier1Decision(index=2, verdict="drop", reason="r2"),
            Tier1Decision(index=0, verdict="keep", reason="r0"),
            Tier1Decision(index=1, verdict="drop", reason="r1"),
        ]
    )
    _stub_run_structured(monkeypatch, response)

    verdicts = tier1.run_batch([_item(0), _item(1), _item(2)], _GOALS)

    assert [v.verdict for v in verdicts] == ["keep", "drop", "drop"]
    assert [v.reason for v in verdicts] == ["r0", "r1", "r2"]


def test_run_batch_empty_input_returns_empty_list(monkeypatch) -> None:
    _stub_agent(monkeypatch)
    # Should not call the agent at all on empty input.
    monkeypatch.setattr(
        tier1, "run_structured", lambda *a, **kw: pytest.fail("should not be called")
    )

    assert tier1.run_batch([], _GOALS) == []


def test_run_batch_rejects_wrong_count(monkeypatch) -> None:
    _stub_agent(monkeypatch)
    _stub_run_structured(
        monkeypatch,
        Tier1Batch(decisions=[Tier1Decision(index=0, verdict="keep", reason="r0")]),
    )

    with pytest.raises(RuntimeError, match="1 decisions for 2 items"):
        tier1.run_batch([_item(0), _item(1)], _GOALS)


def test_run_batch_rejects_wrong_indices(monkeypatch) -> None:
    _stub_agent(monkeypatch)
    _stub_run_structured(
        monkeypatch,
        Tier1Batch(
            decisions=[
                Tier1Decision(index=0, verdict="keep", reason="r0"),
                Tier1Decision(index=5, verdict="drop", reason="r5"),  # bogus index
            ]
        ),
    )

    with pytest.raises(RuntimeError, match="indices"):
        tier1.run_batch([_item(0), _item(1)], _GOALS)


def test_run_single_is_batch_of_one(monkeypatch) -> None:
    _stub_agent(monkeypatch)
    _stub_run_structured(
        monkeypatch,
        Tier1Batch(decisions=[Tier1Decision(index=0, verdict="keep", reason="ok")]),
    )

    verdict = tier1.run(_item(0), _GOALS)

    assert verdict.verdict == "keep"
    assert verdict.reason == "ok"
