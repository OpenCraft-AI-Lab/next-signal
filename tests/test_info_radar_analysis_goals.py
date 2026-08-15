"""Loader tests for info-radar analysis goals."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from next_signal.core import paths
from next_signal.workflows.info_radar_analysis.goals import (
    Goal,
    goals_example_path,
    goals_path,
    load_goals,
    render_goals_block,
)


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


def test_load_goals_missing_file_raises_and_creates_nothing(tmp_path: Path) -> None:
    absent = tmp_path / "absent.yaml"
    with pytest.raises(RuntimeError, match="not found"):
        load_goals(absent)
    # Loading is a pure read: provisioning belongs to bootstrap and to the
    # dashboard's explicit control, never to a read path.
    assert not absent.exists()
    assert list(tmp_path.iterdir()) == []


def test_load_goals_empty_list_raises_distinctly(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(cfg, "goals: []\n")
    # An empty list is a state the operator can deliberately save, so the
    # message must not read like a broken or missing file.
    with pytest.raises(RuntimeError, match="no goals configured") as excinfo:
        load_goals(cfg)
    assert "not found" not in str(excinfo.value)


def test_load_goals_rejects_non_list_goals(tmp_path: Path) -> None:
    cfg = tmp_path / "goals.yaml"
    _write(cfg, "goals: nope\n")
    with pytest.raises(RuntimeError, match="must be a list"):
        load_goals(cfg)


def test_goals_path_resolves_under_state_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "GOALS_FILE", tmp_path / "state" / "goals.yaml")
    resolved = goals_path()
    assert resolved == tmp_path / "state" / "goals.yaml"
    assert "configs" not in resolved.parts


def test_goals_example_is_a_valid_runtime_document() -> None:
    # The example is the seed for every fresh install, so it has to load as-is
    # rather than being a commented-out template.
    goals = load_goals(goals_example_path())
    assert goals, "goals.example.yaml must declare at least one goal"


def test_goals_example_names_pass_the_dashboard_naming_rule() -> None:
    # The loader accepts any non-empty name, but `/goals` only lets the operator
    # ADD kebab-case ones. A seeded name the add form would reject is a trap.
    pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    offenders = [g.name for g in load_goals(goals_example_path()) if not pattern.match(g.name)]
    assert not offenders, f"example goal names must be kebab-case: {offenders}"


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
