"""Parser for ``folocli timeline`` JSON output.

Sample envelope (captured in change ``info-radar`` Appendix B)::

    {
      "ok": true,
      "data": {
        "entries": [
          {"read": false, "view": 1, "entries": {...article...}, "feeds": {...}, ...},
          ...
        ],
        "nextCursor": "2026-05-25T11:00:00.353Z",
        "hasNext": true
      },
      "error": null
    }

Each list element has an awkward inner ``entries`` key holding the actual
article record — we extract from ``el["entries"]`` and keep the whole element
verbatim in ``payload`` (so ``feeds.*`` metadata is preserved).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from paca.collectors.info_radar.schema import RadarItem


def folo_timeline(stdout: str, source_name: str) -> list[RadarItem]:
    """Parse ``folocli timeline -f json`` (default JSON) output."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"folo_timeline: non-JSON stdout: {stdout[:300]!r}") from e

    if not isinstance(envelope, dict) or "ok" not in envelope:
        raise RuntimeError(f"folo_timeline: missing 'ok' envelope field: {envelope!r}")
    if not envelope.get("ok"):
        err = envelope.get("error") or {}
        raise RuntimeError(
            f"folo_timeline: folocli returned ok=false (code={err.get('code')!r}, "
            f"message={err.get('message')!r})"
        )

    data = envelope.get("data") or {}
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise RuntimeError(f"folo_timeline: data.entries is not a list: {type(raw_entries)}")

    items: list[RadarItem] = []
    for raw in raw_entries:
        article = (raw or {}).get("entries")
        if not isinstance(article, dict):
            # Skip malformed elements rather than abort the batch.
            continue
        item_id = article.get("id")
        title = article.get("title")
        if not item_id or not title:
            continue
        items.append(
            RadarItem(
                source_id=str(item_id),
                title=str(title).strip(),
                url=article.get("url"),
                excerpt=_pick_excerpt(article),
                published_at=_parse_iso(article.get("publishedAt")),
                payload=raw,
            )
        )
    return items


def _pick_excerpt(article: dict[str, Any]) -> str | None:
    """Prefer upstream description; fall back to folo's AI summary if present."""
    desc = article.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()
    summary = article.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    # folocli emits e.g. "2026-05-25T18:47:27.745Z"; datetime.fromisoformat
    # accepts that on Python 3.11+ if we replace the trailing Z.
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
