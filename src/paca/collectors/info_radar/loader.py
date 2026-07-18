"""Load + validate ``configs/info_radar/sources.yaml``.

Fails fast on unknown parser names so a typo doesn't silently disable a source.
v1 only resolves literal argv; ``argv_template`` with ``${...}`` placeholders
is reserved for future opencli-style expansion (see design D4 / Appendix A).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from paca.collectors.info_radar.parsers import PARSERS
from paca.core.paths import CONFIGS_DIR

DEFAULT_TIMEOUT_SEC = 60


@dataclass(frozen=True)
class SourceSpec:
    name: str
    enabled: bool
    argv: list[str]
    timeout_sec: int
    parser_name: str

    @property
    def parser(self):
        return PARSERS[self.parser_name]


def sources_path() -> Path:
    return CONFIGS_DIR / "info_radar" / "sources.yaml"


def load_sources(path: Path | None = None) -> list[SourceSpec]:
    """Parse the YAML and return a list of validated source specs."""
    path = path or sources_path()
    if not path.exists():
        raise RuntimeError(
            f"info-radar sources config not found at {path}; "
            "create configs/info_radar/sources.yaml with at least one entry."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_sources = raw.get("sources")
    if not isinstance(raw_sources, list):
        raise RuntimeError(f"{path}: top-level `sources:` must be a list, got {type(raw_sources)}")

    specs: list[SourceSpec] = []
    seen_names: set[str] = set()
    for i, entry in enumerate(raw_sources):
        spec = _validate_entry(entry, index=i, path=path)
        if spec.name in seen_names:
            raise RuntimeError(f"{path}: duplicate source name {spec.name!r}")
        seen_names.add(spec.name)
        specs.append(spec)
    return specs


def _validate_entry(entry: Any, *, index: int, path: Path) -> SourceSpec:
    if not isinstance(entry, dict):
        raise RuntimeError(f"{path}[{index}]: source entry must be a mapping")

    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{path}[{index}]: `name` is required and must be a non-empty string")

    enabled = bool(entry.get("enabled", True))

    cli = entry.get("cli")
    if not isinstance(cli, dict):
        raise RuntimeError(f"{path}[{name}]: `cli` must be a mapping with argv/timeout_sec")

    argv = cli.get("argv")
    if "argv_template" in cli:
        raise RuntimeError(
            f"{path}[{name}]: `argv_template` placeholder expansion is not supported in v1; "
            "use literal `argv` for now."
        )
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        raise RuntimeError(f"{path}[{name}]: `cli.argv` must be a non-empty list of strings")

    timeout_sec = cli.get("timeout_sec", DEFAULT_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or timeout_sec <= 0:
        raise RuntimeError(f"{path}[{name}]: `cli.timeout_sec` must be a positive integer")

    parser_name = entry.get("parser")
    if not isinstance(parser_name, str) or parser_name not in PARSERS:
        raise RuntimeError(
            f"{path}[{name}]: parser {parser_name!r} is not registered; "
            f"known parsers: {sorted(PARSERS)}"
        )

    # Reject unknown keys to surface typos.
    allowed_keys = {"name", "enabled", "cli", "parser"}
    extra = set(entry) - allowed_keys
    if extra:
        raise RuntimeError(f"{path}[{name}]: unknown keys {sorted(extra)}")
    allowed_cli_keys = {"argv", "timeout_sec"}
    extra_cli = set(cli) - allowed_cli_keys
    if extra_cli:
        raise RuntimeError(f"{path}[{name}]: unknown cli keys {sorted(extra_cli)}")

    return SourceSpec(
        name=name,
        enabled=enabled,
        argv=list(argv),
        timeout_sec=timeout_sec,
        parser_name=parser_name,
    )


__all__ = ["SourceSpec", "load_sources", "sources_path", "DEFAULT_TIMEOUT_SEC"]
