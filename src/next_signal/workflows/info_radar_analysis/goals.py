"""Load + validate the runtime goals file in user state.

Reading is a pure read: it never creates, repairs, or seeds the file. Populating
it is a setup step owned by :mod:`next_signal.workflows.info_radar_analysis.provision`
(run from ``scripts/container_bootstrap.sh``) and by the dashboard's explicit
"Start from example" control.

A missing file and an empty ``goals:`` list both abort with ``RuntimeError``, and
carry distinct messages — one means "not set up yet", the other means "you cleared
them". The analysis workflow never silently defaults a goal, because all tier-1 /
tier-2 prompts are written assuming a real declared goal exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from next_signal.core import paths


@dataclass(frozen=True)
class Goal:
    name: str
    description: str
    topics: list[str]
    keywords: list[str]


def goals_path() -> Path:
    """The runtime goals file. Read through ``paths`` so tests can patch it."""
    return paths.GOALS_FILE


def goals_example_path() -> Path:
    """The shipped example, used as the seed source. Never written to."""
    return paths.CONFIGS_DIR / "info_radar" / "goals.example.yaml"


def load_goals(path: Path | None = None) -> list[Goal]:
    """Parse the YAML and return a list of validated goals.

    Never writes: a missing file is reported, not created.

    Fails fast on:
      * missing file
      * empty ``goals:`` list
      * duplicate ``name``
      * unknown top-level or per-entry keys
    """
    path = path or goals_path()
    if not path.exists():
        raise RuntimeError(
            f"info-radar goals file not found at {path}; "
            "configure goals on the dashboard's /goals page"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")

    allowed_top = {"goals"}
    extra_top = set(raw) - allowed_top
    if extra_top:
        raise RuntimeError(f"{path}: unknown top-level keys {sorted(extra_top)}")

    raw_goals = raw.get("goals")
    if not isinstance(raw_goals, list):
        raise RuntimeError(f"{path}: `goals:` must be a list")
    # Distinct from the malformed case above and from a missing file: an empty
    # list is a state the operator can deliberately save from /goals, so the
    # message says so rather than implying the file is broken.
    if not raw_goals:
        raise RuntimeError(
            f"{path}: no goals configured (`goals:` is empty); "
            "add one on the dashboard's /goals page"
        )

    goals: list[Goal] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw_goals):
        goal = _validate_entry(entry, index=i, path=path)
        if goal.name in seen:
            raise RuntimeError(f"{path}: duplicate goal name {goal.name!r}")
        seen.add(goal.name)
        goals.append(goal)
    return goals


_ALLOWED_KEYS = {"name", "description", "topics", "keywords"}


def _validate_entry(entry: Any, *, index: int, path: Path) -> Goal:
    if not isinstance(entry, dict):
        raise RuntimeError(f"{path}[{index}]: goal entry must be a mapping")

    extra = set(entry) - _ALLOWED_KEYS
    if extra:
        raise RuntimeError(f"{path}[{index}]: unknown keys {sorted(extra)}")

    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{path}[{index}]: `name` is required (non-empty string)")

    description = entry.get("description")
    if not isinstance(description, str) or not description:
        raise RuntimeError(f"{path}[{name}]: `description` is required (non-empty string)")

    topics = entry.get("topics") or []
    if not isinstance(topics, list) or not all(isinstance(x, str) for x in topics):
        raise RuntimeError(f"{path}[{name}]: `topics` must be a list of strings")

    keywords = entry.get("keywords") or []
    if not isinstance(keywords, list) or not all(isinstance(x, str) for x in keywords):
        raise RuntimeError(f"{path}[{name}]: `keywords` must be a list of strings")

    return Goal(
        name=name,
        description=description,
        topics=list(topics),
        keywords=list(keywords),
    )


def render_goals_block(goals: list[Goal]) -> str:
    """Render goals as a compact text block for agent prompts."""
    lines: list[str] = []
    for g in goals:
        lines.append(f"## Goal: {g.name}")
        lines.append(g.description)
        if g.topics:
            lines.append("Topics: " + ", ".join(g.topics))
        if g.keywords:
            lines.append("Keywords: " + ", ".join(g.keywords))
        lines.append("")
    return "\n".join(lines).strip()


__all__ = [
    "Goal",
    "load_goals",
    "goals_path",
    "goals_example_path",
    "render_goals_block",
]
