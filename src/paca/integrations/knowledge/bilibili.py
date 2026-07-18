"""Bilibili video extraction for knowledge ingestion."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from functools import cache
from html import unescape
from pathlib import Path
from typing import Any

from opencc import OpenCC

from paca.integrations._helpers import http_client, to_jsonable


def extract_bilibili(url: str) -> dict[str, Any]:
    """Extract Bilibili page metadata and transcript text."""
    with http_client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
        },
        timeout=20,
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    html = response.text
    data = _initial_state(html)
    video = data.get("videoData") or {}
    if not video:
        return to_jsonable({"ok": False, "html": html, "error": "BilibiliMetadataNotFound"})

    subtitle = video.get("subtitle") or {}
    transcript = _public_subtitle(url, subtitle.get("list") or [])
    transcript_source = "public_subtitle" if transcript else None
    if transcript is None:
        transcript = _transcribe_audio_from_video(url)
        transcript_source = "whisper"

    owner = video.get("owner") or {}
    pages = video.get("pages") or []
    pubdate = _unix_time(video.get("pubdate"))
    title = _clean_bilibili_text(video.get("title") or "Bilibili Video")
    owner_name = _clean_bilibili_text(owner.get("name") or "")
    lines = [
        f"# {title}",
        "",
        "## Metadata",
        "",
        f"- Source: {url}",
        f"- BVID: {video.get('bvid') or ''}",
        f"- UP: {owner_name}",
    ]
    if pubdate:
        lines.append(f"- Published: {pubdate}")
    if video.get("duration"):
        lines.append(f"- Duration: {_format_duration(video.get('duration'))}")
    if video.get("desc"):
        lines.extend(["", "## Description", "", _clean_bilibili_block(str(video["desc"]))])
    if pages:
        lines.extend(["", "## Parts", ""])
        for page in pages:
            part = _clean_bilibili_text(page.get("part") or "")
            duration_text = f" ({_format_duration(page.get('duration'))})" if page.get("duration") else ""
            lines.append(f"- P{page.get('page')}: {part}{duration_text}")
    lines.extend(["", "## Transcript", "", transcript or "Transcription returned no text."])

    return to_jsonable(
        {
            "ok": True,
            "html": html,
            "title": title,
            "markdown": "\n".join(lines),
            "transcript": transcript or "",
            "metadata": {
                "bvid": video.get("bvid"),
                "aid": video.get("aid"),
                "cid": video.get("cid"),
                "owner": owner_name,
                "publish_time": pubdate,
                "duration": video.get("duration"),
                "subtitle_available": bool(subtitle.get("list")),
                "transcript_source": transcript_source,
            },
        }
    )


def bilibili_fetch_captions(url: str) -> dict[str, Any]:
    """Lightweight text-proxy fetch for the content collision probe.

    Returns ``{title, description, captions}`` using only the public subtitle
    track — no audio download / whisper fallback (unlike ``extract_bilibili``),
    because the probe only needs an angle-level text proxy of a top-K video,
    not a full ingest. ``captions`` is ``None`` when the video has no public
    subtitle; the caller still gets title + description to judge on.
    """
    with http_client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
        },
        timeout=20,
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    video = _initial_state(response.text).get("videoData") or {}
    subtitle = video.get("subtitle") or {}
    captions = _public_subtitle(url, subtitle.get("list") or [])
    return to_jsonable(
        {
            "title": _clean_bilibili_text(video.get("title") or ""),
            "description": _clean_bilibili_block(str(video.get("desc") or "")),
            "captions": captions,
        }
    )


def _public_subtitle(source_url: str, subtitles: list[dict[str, Any]]) -> str | None:
    if not subtitles:
        return None
    subtitle_url = subtitles[0].get("subtitle_url") or subtitles[0].get("url")
    if not subtitle_url:
        return None
    if subtitle_url.startswith("//"):
        subtitle_url = f"https:{subtitle_url}"
    with http_client(headers={"User-Agent": "Mozilla/5.0", "Referer": source_url}, timeout=20) as client:
        response = client.get(subtitle_url)
        response.raise_for_status()
    body = response.json().get("body") or []
    text = "\n".join(str(item.get("content") or "").strip() for item in body if item.get("content")).strip()
    return _to_simplified_chinese(text) if text else None


def _transcribe_audio_from_video(source_url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="paca-bilibili-") as tmp:
        audio_path = _download_temp_audio(source_url, Path(tmp))
        return _transcribe_audio(audio_path)


def _download_temp_audio(source_url: str, tmp_dir: Path) -> Path:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as e:
        raise RuntimeError("Bilibili transcription requires yt-dlp") from e

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(tmp_dir / "media.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "64"}],
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([source_url])
    candidates = sorted(tmp_dir.glob("media.*"))
    if not candidates:
        raise RuntimeError("yt-dlp did not produce a temporary audio file")
    return candidates[0]


def _transcribe_audio(audio_path: Path) -> str:
    try:
        import whisper
    except ImportError as e:
        raise RuntimeError("Bilibili transcription requires openai-whisper") from e

    model_name = os.environ.get("PACA_WHISPER_MODEL", "base")
    result = whisper.load_model(model_name).transcribe(
        str(audio_path),
        language="zh",
        fp16=False,
        initial_prompt="以下是普通话简体中文转写，请使用简体中文。",
    )
    return _to_simplified_chinese(str(result.get("text") or "").strip())


def _clean_bilibili_text(value: Any) -> str:
    text = _to_simplified_chinese(unescape(str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _clean_bilibili_block(value: str) -> str:
    text = _to_simplified_chinese(unescape(value))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    out: list[str] = []
    paragraph: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith(("-", "*", "•")) or line.endswith("："):
            _flush_paragraph(paragraph, out)
            out.append(line)
        else:
            paragraph.append(line)
    _flush_paragraph(paragraph, out)
    return "\n".join(out).strip()


def _flush_paragraph(paragraph: list[str], out: list[str]) -> None:
    if not paragraph:
        return
    text = paragraph[0]
    for line in paragraph[1:]:
        separator = "" if _touches_cjk(text[-1], line[0]) else " "
        text = f"{text}{separator}{line}"
    out.append(text)
    paragraph.clear()


def _touches_cjk(left: str, right: str) -> bool:
    return bool(re.match(r"[\u4e00-\u9fff]", left) and re.match(r"[\u4e00-\u9fff]", right))


def _format_duration(value: Any) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return ""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _to_simplified_chinese(text: str) -> str:
    if not text:
        return text
    return _opencc().convert(text)


@cache
def _opencc() -> OpenCC:
    return OpenCC("t2s")


def _initial_state(html: str) -> dict[str, Any]:
    match = re.search(r"<script>window\.__INITIAL_STATE__=(.*?);\(function\(\)", html, re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _unix_time(value: Any) -> str | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, UTC).replace(microsecond=0).isoformat()
