"""Tier-1 cheap filter: keep or drop radar_items from title + description.

Batched by default — see design.md §D12. The agent receives up to ~10 items
in a single prompt and returns a parallel array of verdicts; the runner
falls back to single-item calls (via :func:`run`) when a batch fails
validation. Single-item calls are themselves implemented as a batch of
size 1, so there's one agent and one prompt shape.
"""

from __future__ import annotations

import json
from typing import Any

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.workflows.info_radar_analysis._helpers import item_description
from paca.workflows.info_radar_analysis.goals import Goal, render_goals_block
from paca.workflows.info_radar_analysis.schemas import (
    Tier1Batch,
    Tier1Verdict,
)


def run_batch(
    items: list[dict[str, Any]], goals: list[Goal], locale: str = "en"
) -> list[Tier1Verdict]:
    """Send ``items`` to the agent in a single batched prompt; return one
    verdict per input item, in order.

    Raises ``RuntimeError`` if the agent returns the wrong number of
    decisions or wrong indices. Callers (the runner) catch and fall back to
    size-1 calls. The structured-output retry inside ``run_structured``
    handles JSON / schema failures internally with one repair pass.
    """
    if not items:
        return []

    payload = {
        "goals": render_goals_block(goals),
        "items": [
            {
                "index": i,
                "title": item.get("title") or "",
                "description": item_description(item),
            }
            for i, item in enumerate(items)
        ],
    }
    agent = build_from_name("radar_tier1_filter", locale)
    batch = run_structured(agent, json.dumps(payload, ensure_ascii=False), Tier1Batch)

    if len(batch.decisions) != len(items):
        raise RuntimeError(
            f"tier1 batch returned {len(batch.decisions)} decisions for {len(items)} items"
        )
    expected = set(range(len(items)))
    got = {d.index for d in batch.decisions}
    if got != expected:
        raise RuntimeError(
            f"tier1 batch returned indices {sorted(got)}, expected {sorted(expected)}"
        )

    by_index = {d.index: d for d in batch.decisions}
    return [
        Tier1Verdict(verdict=by_index[i].verdict, reason=by_index[i].reason)
        for i in range(len(items))
    ]


def run(item: dict[str, Any], goals: list[Goal], locale: str = "en") -> Tier1Verdict:
    """Single-item convenience — implemented as a batch of size 1.

    Used by the runner's per-item fallback when a batched call fails its
    length / index validation. Keeps the agent / prompt shape uniform.
    """
    [verdict] = run_batch([item], goals, locale)
    return verdict


__all__ = ["run", "run_batch"]
