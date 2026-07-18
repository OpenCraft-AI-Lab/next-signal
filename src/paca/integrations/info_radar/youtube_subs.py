"""Opportunistic native-subtitle extraction for YouTube items.

Used by the info-radar-analysis tier-2 fetch stage to augment the article
content when a feed item is a YouTube video. Never raises — returns ``None``
on any failure and logs at WARN once per process so noisy failures don't
spam the log.

Audio transcription is EXPLICITLY out of scope (see design.md §D3). If the
caller wants ASR, they should reach for ``paca/integrations/knowledge/bilibili.py``'s
audio path.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")
_DEFAULT_LANGS = ("zh-Hans", "zh-Hant", "zh", "en", "en-US", "en-GB")


def fetch_captions(url: str, *, languages: tuple[str, ...] = _DEFAULT_LANGS) -> str | None:
    """Return concatenated transcript text for a YouTube URL, or None.

    Tries youtube-transcript-api first (fast, no download). On any failure,
    falls back to yt-dlp ``--write-auto-sub --skip-download``. If both fail
    or the URL is not parseable, returns ``None``.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        log.warning("youtube_subs_unparseable_url", extra={"url": url})
        return None

    text = _try_transcript_api(video_id, languages)
    if text:
        return text

    text = _try_yt_dlp(url, languages)
    if text:
        return text

    return None


# ---------------------------------------------------------------------------
# URL → video id
# ---------------------------------------------------------------------------


def _extract_video_id(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001 — defensively malformed URLs
        return None
    host = (parsed.netloc or "").lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/", 1)[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None
    if host in {"youtube.com", "m.youtube.com"}:
        # /watch?v=ID
        if parsed.path in {"/watch", "/watch/"}:
            v = parse_qs(parsed.query).get("v")
            if v and _VIDEO_ID_RE.match(v[0]):
                return v[0]
        # /shorts/ID, /embed/ID, /v/ID
        for prefix in ("/shorts/", "/embed/", "/v/"):
            if parsed.path.startswith(prefix):
                candidate = parsed.path[len(prefix):].split("/", 1)[0]
                if _VIDEO_ID_RE.match(candidate):
                    return candidate
    return None


# ---------------------------------------------------------------------------
# Path A: youtube-transcript-api
# ---------------------------------------------------------------------------


def _try_transcript_api(video_id: str, languages: tuple[str, ...]) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        log.warning("youtube_subs_missing_library")
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=list(languages))
    except Exception as e:  # noqa: BLE001 — many provider-specific exception classes
        log.warning("youtube_transcript_api_failed", extra={"video_id": video_id, "error": str(e)})
        return None
    try:
        snippets = list(fetched)
        text = "\n".join((getattr(s, "text", "") or "").strip() for s in snippets)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "youtube_transcript_api_decode_failed", extra={"video_id": video_id, "error": str(e)}
        )
        return None
    return text.strip() or None


# ---------------------------------------------------------------------------
# Path B: yt-dlp --write-auto-sub --skip-download
# ---------------------------------------------------------------------------


def _try_yt_dlp(url: str, languages: tuple[str, ...]) -> str | None:
    with tempfile.TemporaryDirectory(prefix="paca-yt-subs-") as td:
        out = Path(td) / "%(id)s.%(ext)s"
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-format",
            "vtt",
            "--sub-lang",
            ",".join(languages),
            "-o",
            str(out),
            url,
        ]
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=90)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            log.warning("youtube_subs_yt_dlp_failed", extra={"error": str(e)})
            return None
        vtts = sorted(Path(td).glob("*.vtt"))
        if not vtts:
            return None
        text = _vtt_to_text(vtts[0].read_text(errors="ignore"))
        return text or None


def _vtt_to_text(vtt: str) -> str:
    """Strip WEBVTT cues to plain text. Crude but enough for LLM input."""
    lines: list[str] = []
    for line in vtt.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("WEBVTT") or s.startswith("NOTE") or s.startswith("Kind:"):
            continue
        # Skip timestamp lines like "00:00:01.000 --> 00:00:02.000".
        if "-->" in s:
            continue
        # Skip cue identifiers (purely digits).
        if s.isdigit():
            continue
        # Strip simple inline tags.
        s = re.sub(r"<[^>]+>", "", s)
        if s:
            lines.append(s)
    return "\n".join(lines)


__all__ = ["fetch_captions"]
