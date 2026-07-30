"""Fetch full article content via folocli, with opportunistic YouTube subs.

Returns ``(content, content_status)`` where status is one of:
  * ``"full"``     — folocli returned a real article body
  * ``"fallback"`` — fetch failed, returned empty, or returned only a lede;
                     using title+description
"""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any

from paca.integrations.info_radar.folo import entry_get
from paca.integrations.info_radar.youtube_subs import fetch_captions
from paca.workflows.info_radar_analysis._helpers import item_description

log = logging.getLogger(__name__)

# Below this many characters of prose, a `content` payload is a lede, not an
# article. Paywalled publishers return exactly that, and it measured identical
# to the item's own excerpt — calling it "full" makes tier-2 read an absence of
# detail as an absence of evidence. Real articles run 3000+ chars of text.
_MIN_ARTICLE_CHARS = 200

_DROP_BLOCK = re.compile(r"<(script|style)\b.*?</\1\s*>", re.I | re.S)
_BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|tr|blockquote)\s*>|<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_BLANK_RUN = re.compile(r"\n{3,}")


def _to_text(html: str) -> str:
    """Flatten feed HTML to plain text, keeping paragraph breaks.

    Folo returns raw feed markup. For some sources 86-91% of the payload is
    tags — mostly image URLs and tracking pixels — which both burns the tier-2
    content budget and pushes real prose past the 16k truncation.
    """
    text = _DROP_BLOCK.sub("", html)
    text = _BLOCK_END.sub("\n", text)
    text = unescape(_TAG.sub("", text))
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_RUN.sub("\n\n", text).strip()


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
    content = _to_text(str(content))
    if len(content) < _MIN_ARTICLE_CHARS:
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
