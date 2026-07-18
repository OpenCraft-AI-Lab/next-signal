"""Tests for the info-radar analysis fetch stage (folocli content + fallback)."""

from __future__ import annotations

from paca.workflows.info_radar_analysis.stages import fetch as fetch_mod


def test_fetch_returns_full_content(monkeypatch) -> None:
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": "<p>body</p>"})

    content, status = fetch_mod.run({"source_id": "abc", "title": "T", "excerpt": "E"})

    assert status == "full"
    assert content == "<p>body</p>"


def test_fetch_failure_falls_back_to_title_and_excerpt(monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_mod,
        "entry_get",
        lambda sid: (_ for _ in ()).throw(RuntimeError("folocli down")),
    )

    content, status = fetch_mod.run({"source_id": "abc", "title": "T", "excerpt": "E"})

    assert status == "fallback"
    assert content == "# T\n\nE"


def test_fetch_empty_content_falls_back_to_payload_description(monkeypatch) -> None:
    """Empty body + no excerpt: the description is dug out of payload.entries."""
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": "   "})
    item = {
        "source_id": "abc",
        "title": "T",
        "payload": {"entries": {"description": "D"}},
    }

    content, status = fetch_mod.run(item)

    assert status == "fallback"
    assert content == "# T\n\nD"


def test_fetch_appends_youtube_captions(monkeypatch) -> None:
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": "body"})
    monkeypatch.setattr(fetch_mod, "fetch_captions", lambda url: "caption line")
    item = {"source_id": "abc", "title": "T", "url": "https://youtu.be/abc12345678"}

    content, status = fetch_mod.run(item)

    assert status == "full"
    assert content.startswith("body")
    assert "## Captions" in content
    assert "caption line" in content


def test_fetch_caption_failure_keeps_full_content(monkeypatch) -> None:
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": "body"})
    monkeypatch.setattr(
        fetch_mod,
        "fetch_captions",
        lambda url: (_ for _ in ()).throw(ValueError("yt-dlp exploded")),
    )
    item = {"source_id": "abc", "title": "T", "url": "https://youtu.be/abc12345678"}

    assert fetch_mod.run(item) == ("body", "full")
