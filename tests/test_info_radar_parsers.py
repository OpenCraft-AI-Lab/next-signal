"""Smoke tests for info-radar parsers.

Fixtures are minimized canned outputs based on the real folocli timeline JSON
captured during change ``info-radar`` task 1.2 (see design.md Appendix B).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from paca.collectors.info_radar.parsers.folo import folo_timeline


def _envelope(entries: list[dict]) -> str:
    return json.dumps(
        {
            "ok": True,
            "data": {"entries": entries, "nextCursor": None, "hasNext": False},
            "error": None,
        }
    )


def _make_entry(*, article_id: str, **overrides: object) -> dict:
    article = {
        "id": article_id,
        "title": "Sample title",
        "url": f"https://example.com/{article_id}",
        "description": "Sample description.",
        "publishedAt": "2026-05-25T18:47:27.745Z",
        "summary": None,
    }
    article.update({k: v for k, v in overrides.items() if k in article or k != "wrap"})
    entry = {
        "read": False,
        "view": 0,
        "from": ["feed"],
        "entries": article,
        "feeds": {"id": "feed-1", "url": "https://example.com/feed", "title": "Demo"},
        "subscriptions": {"category": "AI", "title": None},
        "settings": {},
    }
    if overrides.get("wrap"):
        entry.update(overrides["wrap"])  # type: ignore[arg-type]
    return entry


def test_folo_timeline_happy_path() -> None:
    stdout = _envelope(
        [
            _make_entry(article_id="1127262502032277504"),
            _make_entry(article_id="1126959751247212544", title="Second"),
        ]
    )

    items = folo_timeline(stdout, "folo_test")

    assert len(items) == 2
    first, second = items
    assert first.source_id == "1127262502032277504"
    assert first.title == "Sample title"
    assert first.url == "https://example.com/1127262502032277504"
    assert first.excerpt == "Sample description."
    assert first.published_at == datetime(2026, 5, 25, 18, 47, 27, 745000, tzinfo=timezone.utc)
    assert first.payload["entries"]["id"] == "1127262502032277504"
    assert second.title == "Second"


def test_folo_timeline_falls_back_to_summary_when_description_blank() -> None:
    entries = [_make_entry(article_id="abc")]
    entries[0]["entries"]["description"] = ""
    entries[0]["entries"]["summary"] = "AI summary fallback"

    items = folo_timeline(_envelope(entries), "s")

    assert items[0].excerpt == "AI summary fallback"


def test_folo_timeline_handles_missing_published_at() -> None:
    entries = [_make_entry(article_id="abc")]
    entries[0]["entries"]["publishedAt"] = None

    items = folo_timeline(_envelope(entries), "s")

    assert items[0].published_at is None


def test_folo_timeline_raises_on_ok_false() -> None:
    stdout = json.dumps(
        {"ok": False, "data": None, "error": {"code": "UNAUTHORIZED", "message": "no token"}}
    )

    with pytest.raises(RuntimeError, match="UNAUTHORIZED"):
        folo_timeline(stdout, "s")


def test_folo_timeline_raises_on_non_json() -> None:
    with pytest.raises(RuntimeError, match="non-JSON"):
        folo_timeline("not json", "s")


def test_folo_timeline_raises_on_missing_envelope() -> None:
    with pytest.raises(RuntimeError, match="missing 'ok'"):
        folo_timeline('{"data": []}', "s")


def test_folo_timeline_skips_malformed_entries_without_aborting() -> None:
    entries = [
        _make_entry(article_id="good-1"),
        {"entries": None},  # malformed — no article dict
        _make_entry(article_id="good-2"),
        {"entries": {"id": "no-title"}},  # malformed — no title
    ]

    items = folo_timeline(_envelope(entries), "s")

    assert [i.source_id for i in items] == ["good-1", "good-2"]
