"""Fetch full article content via folocli, with opportunistic YouTube subs.

Returns ``(content, content_status)`` where status is one of:
  * ``"full"``     — folocli returned a non-empty body
  * ``"fallback"`` — fetch failed or returned empty; using title+description
"""

from __future__ import annotations

import logging
from typing import Any

from paca.integrations.info_radar.folo import entry_get
from paca.integrations.info_radar.youtube_subs import fetch_captions
from paca.workflows.info_radar_analysis._helpers import item_description

log = logging.getLogger(__name__)


def run(item: dict[str, Any]) -> tuple[str, str]:
    """Return ``(content, content_status)`` for a tier-1-kept item."""
    title = item.get("title") or ""
    description = item_description(item)
    fallback_body = (
        f"# {title}\n\n{description}".strip() if description else title or ""
    )

    source_id = item.get("source_id") or ""
    try:
        entries = entry_get(source_id)
    except RuntimeError as e:
        log.warning(
            "info_radar_fetch_failed",
            extra={"source_id": source_id, "error": str(e)},
        )
        return fallback_body, "fallback"

    content = (entries.get("content") if isinstance(entries, dict) else None) or ""
    content = str(content).strip()
    if not content:
        return fallback_body, "fallback"

    # Opportunistic YouTube subtitles. Skip silently on any failure.
    subs = _maybe_youtube_subs(item)
    if subs:
        content = f"{content}\n\n## Captions\n\n{subs}"

    return content, "full"


def _maybe_youtube_subs(item: dict[str, Any]) -> str | None:
    payload = item.get("payload") or {}
    if not isinstance(payload, dict):
        return None
    entries = payload.get("entries") or {}
    feeds = payload.get("feeds") or {}
    candidate_url = (
        (entries.get("url") if isinstance(entries, dict) else None)
        or item.get("url")
        or ""
    )
    feed_url = feeds.get("url") if isinstance(feeds, dict) else ""

    is_youtube = (
        "youtube.com" in (candidate_url or "")
        or "youtu.be" in (candidate_url or "")
        or "youtube" in (feed_url or "").lower()
    )
    if not is_youtube or not candidate_url:
        return None
    try:
        return fetch_captions(candidate_url)
    except Exception as e:  # noqa: BLE001 — defensive; the helper already swallows
        log.warning("youtube_subs_unexpected_raise", extra={"error": str(e)})
        return None
