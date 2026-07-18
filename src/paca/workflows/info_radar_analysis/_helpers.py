"""Shared helpers used across info-radar-analysis stages."""

from __future__ import annotations

from typing import Any


def item_description(item: dict[str, Any]) -> str:
    """Return the best-available short description for a radar_items row.

    Prefers the parser-populated ``excerpt`` column (the folo_timeline parser
    already picks ``description`` then falls back to ``summary``). Falls back
    to digging into ``payload.entries`` for parsers that may not have filled
    ``excerpt``. Returns empty string when nothing usable is present.
    """
    excerpt = item.get("excerpt")
    if excerpt:
        return str(excerpt)
    payload = item.get("payload") or {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if isinstance(entries, dict):
        for key in ("description", "summary"):
            v = entries.get(key)
            if v:
                return str(v)
    return ""
