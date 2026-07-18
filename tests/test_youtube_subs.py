"""Tests for opportunistic YouTube subtitle extraction."""

from __future__ import annotations

import pytest

from paca.integrations.info_radar import youtube_subs


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=abc12345678&t=20s", "abc12345678"),
        ("https://m.youtube.com/watch?v=abc12345678", "abc12345678"),
        ("https://youtu.be/abc12345678", "abc12345678"),
        ("https://www.youtube.com/shorts/abc12345678", "abc12345678"),
        ("https://www.youtube.com/embed/abc12345678", "abc12345678"),
    ],
)
def test_extract_video_id_recognizes_common_forms(url: str, expected: str) -> None:
    assert youtube_subs._extract_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    ["", "https://example.com/abc", "https://youtube.com/", "not a url"],
)
def test_extract_video_id_returns_none_for_unparseable(url: str) -> None:
    assert youtube_subs._extract_video_id(url) is None


# ---------------------------------------------------------------------------
# fetch_captions — happy path via youtube-transcript-api stub
# ---------------------------------------------------------------------------


class _Snippet:
    def __init__(self, text: str):
        self.text = text


class _FakeApi:
    def __init__(self, snippets: list[_Snippet] | Exception):
        self._snippets = snippets

    def fetch(self, video_id: str, languages):  # noqa: ARG002
        if isinstance(self._snippets, Exception):
            raise self._snippets
        return self._snippets


def test_fetch_captions_uses_transcript_api(monkeypatch) -> None:
    fake_api = _FakeApi([_Snippet("hello"), _Snippet("world")])
    monkeypatch.setattr(
        "youtube_transcript_api.YouTubeTranscriptApi",
        lambda *a, **kw: fake_api,
    )

    result = youtube_subs.fetch_captions("https://www.youtube.com/watch?v=abc12345678")

    assert result == "hello\nworld"


def test_fetch_captions_returns_none_when_api_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "youtube_transcript_api.YouTubeTranscriptApi",
        lambda *a, **kw: _FakeApi(RuntimeError("rate limited")),
    )
    # Block the yt-dlp fallback too so the test stays hermetic.
    monkeypatch.setattr(youtube_subs, "_try_yt_dlp", lambda *a, **kw: None)

    result = youtube_subs.fetch_captions("https://www.youtube.com/watch?v=abc12345678")

    assert result is None


def test_fetch_captions_returns_none_for_non_youtube_url(monkeypatch) -> None:
    # Should bail before either path is even attempted.
    monkeypatch.setattr(
        youtube_subs,
        "_try_transcript_api",
        lambda *a, **kw: pytest.fail("should not be called"),
    )
    monkeypatch.setattr(
        youtube_subs,
        "_try_yt_dlp",
        lambda *a, **kw: pytest.fail("should not be called"),
    )

    assert youtube_subs.fetch_captions("https://example.com/foo") is None


def test_vtt_to_text_strips_timing_and_tags() -> None:
    sample = """WEBVTT
Kind: captions

00:00:00.000 --> 00:00:02.000
<v Speaker>hello world

00:00:02.000 --> 00:00:04.000
second line
"""
    out = youtube_subs._vtt_to_text(sample)
    assert "hello world" in out
    assert "second line" in out
    assert "00:00" not in out
    assert "<v" not in out
