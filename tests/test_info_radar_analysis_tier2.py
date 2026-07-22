"""Tests for the tier-2 stage's deterministic score ceilings."""

from __future__ import annotations

from paca.workflows.info_radar_analysis.schemas import Tier2Analysis
from paca.workflows.info_radar_analysis.stages.tier2 import _apply_ceilings


def _analysis(score: int, tags: list[str]) -> Tier2Analysis:
    return Tier2Analysis(display_title="t", summary="s", impact="i", score=score, tags=tags)


def test_opinion_above_ceiling_is_clamped() -> None:
    assert _apply_ceilings(_analysis(72, ["opinion", "agent"])).score == 65


def test_opinion_at_or_below_ceiling_untouched() -> None:
    assert _apply_ceilings(_analysis(58, ["opinion"])).score == 58


def test_frontier_voice_is_exempt() -> None:
    assert _apply_ceilings(_analysis(88, ["frontier-voice", "talk"])).score == 88


def test_opinion_tag_match_is_case_insensitive() -> None:
    assert _apply_ceilings(_analysis(80, ["Opinion"])).score == 65


def test_no_tags_untouched() -> None:
    assert _apply_ceilings(_analysis(90, [])).score == 90


def test_tier2_prompt_variants_instruct_display_title() -> None:
    """Both locale variants must carry the display_title field (kept in sync)."""
    from paca.core.config import PROMPTS_DIR

    for locale in ("zh", "en"):
        text = (PROMPTS_DIR / "agents" / f"radar_tier2_impact.{locale}.md").read_text(
            encoding="utf-8"
        )
        assert "display_title" in text
