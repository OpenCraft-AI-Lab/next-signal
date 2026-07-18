"""Tier-2 impact analysis: produce summary + impact_md + score + tags."""

from __future__ import annotations

import json
from typing import Any

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.workflows.info_radar_analysis.goals import Goal, render_goals_block
from paca.workflows.info_radar_analysis.schemas import Tier2Analysis

# Cap content length passed to the LLM. Full articles can be 50k+ chars; the
# tail rarely carries new signal once we're past the first ~16k.
_MAX_CONTENT_CHARS = 16000

# The prompt states this ceiling too, but the model occasionally leaks past
# it. Goals-listed high-signal individuals are exempt: the prompt has the
# model tag their content `frontier-voice` instead of `opinion`.
_OPINION_CEILING = 65


def _apply_ceilings(analysis: Tier2Analysis) -> Tier2Analysis:
    if analysis.score > _OPINION_CEILING and any(
        t.strip().lower() == "opinion" for t in analysis.tags
    ):
        analysis.score = _OPINION_CEILING
    return analysis


def run(
    item: dict[str, Any],
    content: str,
    content_status: str,
    goals: list[Goal],
) -> Tier2Analysis:
    """Ask radar_tier2_impact for a goal-grounded analysis of the item."""
    truncated = content[:_MAX_CONTENT_CHARS]
    payload = {
        "goals": render_goals_block(goals),
        "title": item.get("title") or "",
        "url": item.get("url"),
        "content": truncated,
        "content_status": content_status,
    }
    agent = build_from_name("radar_tier2_impact")
    analysis = run_structured(agent, json.dumps(payload, ensure_ascii=False), Tier2Analysis)
    return _apply_ceilings(analysis)
