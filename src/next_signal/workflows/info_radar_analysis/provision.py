"""Seed the runtime goals file from the shipped example. Setup only, never a read path.

Rationale for keeping this out of ``load_goals`` and for guarding on existence
rather than goal count: `openspec/specs/info-radar-analysis`, "Runtime goals file
provisioning".
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from next_signal.workflows.info_radar_analysis.goals import goals_example_path, goals_path

Outcome = Literal["present", "seeded"]


def provision_goals_file(
    *,
    target: Path | None = None,
    example: Path | None = None,
) -> Outcome:
    """Copy the example into place when the runtime goals file is absent.

    The guard is the target's existence, never its goal count: an empty ``goals:``
    list is a state the operator can deliberately save from ``/goals``, and
    restoring the examples on the next ``docker compose up`` would look like a bug.
    """
    target = target or goals_path()
    example = example or goals_example_path()

    if target.exists():
        return "present"
    if not example.exists():
        raise RuntimeError(f"cannot provision {target}: {example} does not exist")

    _atomic_copy(example, target)
    return "seeded"


def _atomic_copy(source: Path, target: Path) -> None:
    """Copy through a temp file beside the target, so no reader observes a partial file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.replace(target)


def main() -> None:
    """Entry point for ``python -m next_signal.workflows.info_radar_analysis.provision``."""
    target = goals_path()
    if provision_goals_file() == "present":
        print(f"[goals] {target} already exists, leaving it alone")
    else:
        print(f"[goals] seeded {target} from {goals_example_path()}")


if __name__ == "__main__":
    main()


__all__ = ["Outcome", "provision_goals_file", "main"]
