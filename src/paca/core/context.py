"""Shared static context — concatenated from every ``prompts/_shared/*.md``
and prepended to every agent's instructions.

Pattern borrowed from agno-agi/investment-team (`context/loader.py`). The
files are read once at module-import time and cached; the dashboard's
hot-reload path can call ``reload()`` to pick up edits without restarting
the process.

Filenames sort lexicographically — prefix with two-digit numbers
(``00_house_rules.md``, ``10_user_profile.md``) to control the order.
Files starting with ``_`` are skipped, so you can stash drafts.
"""

from __future__ import annotations

from paca.core.paths import PROMPTS_DIR

SHARED_DIR = PROMPTS_DIR / "_shared"

_cached: str | None = None


def shared_context() -> str:
    """Return the concatenated shared-context string. Cached after first call."""
    global _cached
    if _cached is None:
        _cached = _load()
    return _cached


def reload() -> str:
    """Force re-read from disk. Called by the dashboard hot-reload hook."""
    global _cached
    _cached = _load()
    return _cached


def _load() -> str:
    if not SHARED_DIR.exists():
        return ""
    sections: list[str] = []
    for path in sorted(SHARED_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        sections.append(path.read_text(encoding="utf-8").rstrip())
    return "\n\n---\n\n".join(sections)
