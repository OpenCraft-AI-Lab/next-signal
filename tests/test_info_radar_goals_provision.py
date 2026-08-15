"""Provisioning tests for the runtime goals file.

The rule these exist to protect: provisioning is guarded on the runtime file's
*existence*, never on its goal count. A count-based guard would restore the
example goals on the next `docker compose up` after an operator deliberately
cleared them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from next_signal.workflows.info_radar_analysis.goals import load_goals
from next_signal.workflows.info_radar_analysis.provision import provision_goals_file

EXAMPLE = """
goals:
  - name: seeded
    description: "from the shipped example"
"""

CURATED = """
goals:
  - name: curated
    description: "the operator's own"
"""


@pytest.fixture
def sources(tmp_path: Path) -> tuple[Path, Path]:
    """Return (target, example); only the example exists on disk."""
    example = tmp_path / "repo" / "goals.example.yaml"
    example.parent.mkdir(parents=True, exist_ok=True)
    example.write_text(EXAMPLE, encoding="utf-8")
    return (tmp_path / "state" / "goals.yaml", example)


def _provision(sources: tuple[Path, Path]) -> str:
    target, example = sources
    return provision_goals_file(target=target, example=example)


def test_seeds_from_example_on_fresh_install(sources) -> None:
    target, _ = sources
    assert _provision(sources) == "seeded"
    [goal] = load_goals(target)
    assert goal.name == "seeded"


def test_is_idempotent_and_never_overwrites(sources) -> None:
    target, _ = sources
    assert _provision(sources) == "seeded"
    target.write_text(CURATED, encoding="utf-8")

    assert _provision(sources) == "present"

    [goal] = load_goals(target)
    assert goal.name == "curated"


def test_does_not_repopulate_a_deliberately_emptied_list(sources) -> None:
    """The regression test for the guard: existence, not goal count."""
    target, _ = sources
    _provision(sources)
    target.write_text("goals: []\n", encoding="utf-8")

    assert _provision(sources) == "present"

    assert target.read_text(encoding="utf-8") == "goals: []\n"


def test_raises_when_the_example_is_missing(sources) -> None:
    target, example = sources
    example.unlink()
    with pytest.raises(RuntimeError, match="cannot provision"):
        _provision(sources)
    assert not target.exists(), "a failed provision must not leave a partial file"


def test_writes_atomically_leaving_no_temp_file(sources) -> None:
    target, _ = sources
    _provision(sources)
    assert target.exists()
    assert list(target.parent.iterdir()) == [target], "temp file must not survive"
