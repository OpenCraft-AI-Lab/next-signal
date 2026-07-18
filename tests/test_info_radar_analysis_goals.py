"""Loader tests for info-radar analysis goals."""

from __future__ import annotations

from pathlib import Path

import pytest

from paca.workflows.info_radar_analysis.goals import Goal, load_goals, render_goals_block


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_load_goals_accepts_valid_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(
        cfg,
        """
goals:
  - name: ai_research
    description: "Stay current on AI."
    topics: ["LLM inference"]
    keywords: ["mlx", "vllm"]
""",
    )

    [goal] = load_goals(cfg)

    assert isinstance(goal, Goal)
    assert goal.name == "ai_research"
    assert goal.description == "Stay current on AI."
    assert goal.topics == ["LLM inference"]
    assert goal.keywords == ["mlx", "vllm"]


def test_load_goals_defaults_optional_lists(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(
        cfg,
        """
goals:
  - name: a
    description: "x"
""",
    )

    [goal] = load_goals(cfg)

    assert goal.topics == []
    assert goal.keywords == []


def test_load_goals_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not found"):
        load_goals(tmp_path / "absent.yaml")


def test_load_goals_empty_list_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(cfg, "goals: []\n")
    with pytest.raises(RuntimeError, match="non-empty list"):
        load_goals(cfg)


def test_load_goals_duplicate_names_raise(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(
        cfg,
        """
goals:
  - name: dup
    description: "first"
  - name: dup
    description: "second"
""",
    )
    with pytest.raises(RuntimeError, match="duplicate goal name 'dup'"):
        load_goals(cfg)


def test_load_goals_unknown_top_level_key_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(
        cfg,
        """
goals:
  - name: a
    description: "x"
extras: oops
""",
    )
    with pytest.raises(RuntimeError, match="unknown top-level keys"):
        load_goals(cfg)


def test_load_goals_unknown_entry_key_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(
        cfg,
        """
goals:
  - name: a
    description: "x"
    bogus: 1
""",
    )
    with pytest.raises(RuntimeError, match="unknown keys"):
        load_goals(cfg)


def test_render_goals_block_includes_topics_and_keywords() -> None:
    goals = [
        Goal(
            name="g1",
            description="desc.",
            topics=["topic-a"],
            keywords=["kw-1"],
        )
    ]
    block = render_goals_block(goals)
    assert "## Goal: g1" in block
    assert "desc." in block
    assert "topic-a" in block
    assert "kw-1" in block
