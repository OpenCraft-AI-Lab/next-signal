"""Populate the runtime goals file. Setup only — never called from a read path.

``load_goals`` deliberately does not repair a missing file: a filesystem write
hidden inside a read would fire from tests, health checks, and dry runs, and a
fresh unattended run would score against the shipped example goals instead of
failing loudly. Provisioning is therefore an explicit step, invoked from
``scripts/container_bootstrap.sh`` and from the dashboard's "Start from example"
control.

Two ordering rules carry the correctness of this module:

1. **Migrate before seeding.** A curated ``configs/info_radar/goals.yaml`` left
   over from before goals moved into user state is copied first, so upgrading
   never replaces a real goals list with the samples.
2. **Guard on the runtime file's existence, never on its goal count.** An empty
   ``goals:`` list is a state the operator can deliberately save from ``/goals``;
   restoring the examples on the next ``docker compose up`` would be
   indistinguishable from a bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from next_signal.core import paths
from next_signal.workflows.info_radar_analysis.goals import goals_example_path, goals_path

Outcome = Literal["present", "migrated", "seeded"]


def legacy_goals_path() -> Path:
    """Where goals lived before they moved to user state. Read-only; never deleted."""
    return paths.CONFIGS_DIR / "info_radar" / "goals.yaml"


def provision_goals_file(
    *,
    target: Path | None = None,
    legacy: Path | None = None,
    example: Path | None = None,
) -> Outcome:
    """Ensure the runtime goals file exists. Returns what was done.

    ``present`` means the file was already there and was left byte-identical,
    whatever it contained — including an empty ``goals:`` list.
    """
    target = target or goals_path()
    legacy = legacy or legacy_goals_path()
    example = example or goals_example_path()

    # Existence, not content: see rule 2 in the module docstring.
    if target.exists():
        return "present"

    if legacy.exists():
        source, outcome = legacy, "migrated"
    elif example.exists():
        source, outcome = example, "seeded"
    else:
        raise RuntimeError(
            f"cannot provision {target}: neither {legacy} nor {example} exists"
        )

    _atomic_copy(source, target)
    return outcome


def _atomic_copy(source: Path, target: Path) -> None:
    """Copy via a temp file beside the target, then rename.

    The temp file shares the target's directory so the rename stays within one
    filesystem — the state volume — and no reader can observe a partial file.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.replace(target)


def main() -> None:
    """Entry point for ``python -m next_signal.workflows.info_radar_analysis.provision``."""
    target = goals_path()
    outcome = provision_goals_file()
    if outcome == "present":
        print(f"[goals] {target} already exists, leaving it alone")
    elif outcome == "migrated":
        print(f"[goals] migrated {legacy_goals_path()} -> {target}")
    else:
        print(f"[goals] seeded {target} from {goals_example_path()}")


if __name__ == "__main__":
    main()


__all__ = ["Outcome", "legacy_goals_path", "provision_goals_file", "main"]
