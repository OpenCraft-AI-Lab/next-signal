"""Tests for the info-radar analysis fetch stage (folocli content + fallback)."""

from __future__ import annotations

from paca.workflows.info_radar_analysis.stages import fetch as fetch_mod

# Long enough to clear _MIN_ARTICLE_CHARS — a real article body.
_BODY = "正文段落。" * 60
_ARTICLE = f"<p>{_BODY}</p>"


def test_fetch_returns_full_content(monkeypatch) -> None:
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": _ARTICLE})

    content, status = fetch_mod.run({"source_id": "abc", "title": "T", "excerpt": "E"})

    assert status == "full"
    assert content == _BODY


def test_fetch_strips_markup_and_keeps_paragraph_breaks(monkeypatch) -> None:
    """Image tags and entities are dropped; block boundaries become newlines."""
    html = (
        '<img width="1280" src="https://img.example/x?size=1.5&#x26;width=1280" alt="">'
        f"<p>{_BODY}</p><p>第二段&amp;结尾</p><script>tracker()</script>"
    )
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": html})

    content, status = fetch_mod.run({"source_id": "abc", "title": "T", "excerpt": "E"})

    assert status == "full"
    assert content == f"{_BODY}\n第二段&结尾"
    assert "<" not in content and "img.example" not in content
    assert "tracker()" not in content


def test_fetch_lede_only_content_is_marked_fallback(monkeypatch) -> None:
    """Paywalled feeds return a lede under `content`; that is not a full article.

    Calling it "full" makes tier-2 read an absence of detail as an absence of
    evidence, so it falls back to title+excerpt and says so.
    """
    lede = '<img width="1280" src="https://images.wsj.net/im-29072909?size=1.5" alt="">'
    lede += "<p>Alphabet将预估资本支出上调至1,950亿至2,050亿美元。</p>"
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": lede})

    content, status = fetch_mod.run({"source_id": "abc", "title": "T", "excerpt": "E"})

    assert status == "fallback"
    assert content == "# T\n\nE"


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
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": _ARTICLE})
    monkeypatch.setattr(fetch_mod, "fetch_captions", lambda url: "caption line")
    item = {"source_id": "abc", "title": "T", "url": "https://youtu.be/abc12345678"}

    content, status = fetch_mod.run(item)

    assert status == "full"
    assert content.startswith(_BODY)
    assert "## Captions" in content
    assert "caption line" in content


def test_fetch_caption_failure_keeps_full_content(monkeypatch) -> None:
    monkeypatch.setattr(fetch_mod, "entry_get", lambda sid: {"content": _ARTICLE})
    monkeypatch.setattr(
        fetch_mod,
        "fetch_captions",
        lambda url: (_ for _ in ()).throw(ValueError("yt-dlp exploded")),
    )
    item = {"source_id": "abc", "title": "T", "url": "https://youtu.be/abc12345678"}

    assert fetch_mod.run(item) == (_BODY, "full")
