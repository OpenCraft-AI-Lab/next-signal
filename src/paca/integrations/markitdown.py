"""MarkItDown conversion bridge for knowledge ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paca.integrations._helpers import to_jsonable, truncate


def convert_source(
    source: str,
    max_chars: int = 100000,
    *,
    youtube_transcript_languages: list[str] | None = None,
) -> dict[str, Any]:
    """Convert a local path or URL to markdown with MarkItDown.

    `youtube_transcript_languages` is forwarded to MarkItDown's YouTube converter
    as a priority list — it tries each language in order and falls back to the
    next. Pass e.g. `["zh-Hans", "zh-CN", "zh", "en"]` to prefer the original
    Chinese transcript over YouTube's auto-translated English captions.
    """
    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise RuntimeError("MarkItDown conversion requires markitdown") from e

    converter = MarkItDown(enable_plugins=False)
    extra: dict[str, Any] = {}
    if youtube_transcript_languages:
        extra["youtube_transcript_languages"] = youtube_transcript_languages
    path = Path(source).expanduser()
    if path.exists():
        result = converter.convert_local(str(path), **extra)
    else:
        result = converter.convert_url(source, **extra)

    markdown = str(getattr(result, "text_content", "") or getattr(result, "markdown", "") or "").strip()
    return to_jsonable(
        {
            "ok": bool(markdown),
            "source": "markitdown",
            "source_value": source,
            "title": getattr(result, "title", None),
            "markdown": truncate(markdown, max_chars),
        }
    )
