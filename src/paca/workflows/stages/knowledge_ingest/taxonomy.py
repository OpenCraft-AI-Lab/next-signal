"""Knowledge wiki taxonomy: classifiable categories and the freshness model.

Loaded from `configs/knowledge_taxonomy.yaml`, the single source of truth shared
by the classify step (category list) and the persist step (freshness tiers).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from paca.core import paths

TAXONOMY_PATH = paths.CONFIGS_DIR / "knowledge_taxonomy.yaml"


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict[str, Any]:
    """Load the wiki taxonomy: freshness tiers and per-category defaults."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "freshness" not in data or "categories" not in data:
        raise RuntimeError(f"invalid knowledge taxonomy: {path}")
    return data


def category_paths(taxonomy: dict[str, Any]) -> list[str]:
    """Return the classifiable category paths in declaration order."""
    return [str(entry["path"]) for entry in taxonomy["categories"]]
