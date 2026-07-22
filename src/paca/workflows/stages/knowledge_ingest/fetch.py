"""Fetch step: detect the source type and produce a populated `KnowledgeArtifact`."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from paca.integrations._helpers import http_client
from paca.integrations.knowledge.bilibili import extract_bilibili
from paca.integrations.knowledge.github import extract_github
from paca.integrations.knowledge.opencli import opencli_weixin_download
from paca.integrations.markitdown import convert_source
from paca.workflows.stages.knowledge_ingest.artifact import KnowledgeArtifact, validate_category
from paca.workflows.stages.knowledge_ingest.classify import detect_source_type
from paca.workflows.stages.knowledge_ingest.raw_store import copy_raw_file, raw_dir, write_raw_text


def _new_artifact(value: str, source_type: str, category: str) -> KnowledgeArtifact:
    return KnowledgeArtifact(
        value=value,
        source_type=source_type,
        digest=hashlib.sha256(value.encode("utf-8")).hexdigest()[:12],
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        category=category,
    )


def fetch_markdown(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "markdown", category)
    raw_path = copy_raw_file(value, artifact.digest, "markdown")
    artifact.raw_path = raw_path
    artifact.title = raw_path.stem
    artifact.markdown = raw_path.read_text(encoding="utf-8")
    return artifact


def fetch_markitdown(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "markitdown", category)
    return _populate_markitdown(artifact, value)


def fetch_youtube(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "youtube", category)
    return _populate_markitdown(
        artifact, value, youtube_transcript_languages=_youtube_transcript_languages()
    )


# Default chain prefers original-language captions over YouTube's auto-translated
# English. Most ingest targets are Chinese-language videos; English videos still
# resolve via the `en` fallback at the end. Override with PACA_YOUTUBE_TRANSCRIPT_LANGS
# (comma-separated, e.g. "ja,en").
_DEFAULT_YT_LANGS = ["zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW", "en"]


def _youtube_transcript_languages() -> list[str]:
    raw = os.environ.get("PACA_YOUTUBE_TRANSCRIPT_LANGS", "").strip()
    if not raw:
        return list(_DEFAULT_YT_LANGS)
    return [code.strip() for code in raw.split(",") if code.strip()]


def _populate_markitdown(
    artifact: KnowledgeArtifact,
    value: str,
    *,
    youtube_transcript_languages: list[str] | None = None,
) -> KnowledgeArtifact:
    convert_value = value
    if not _is_url(value):
        raw_path = copy_raw_file(value, artifact.digest, artifact.source_type)
        artifact.raw_path = raw_path
        convert_value = str(raw_path)

    result = convert_source(
        convert_value, youtube_transcript_languages=youtube_transcript_languages
    )
    if not result.get("ok"):
        raise RuntimeError("MarkItDown returned no markdown")
    artifact.title = result.get("title") or _title_from_value(value)
    artifact.markdown = result["markdown"]
    artifact.metadata["converter"] = "markitdown"
    if artifact.source_type == "youtube":
        write_raw_text(
            "youtube",
            artifact.digest,
            "conversion.json",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
    return artifact


def fetch_web(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "web", category)
    with http_client(timeout=20) as client:
        response = _get_public_web(client, value)
        response.raise_for_status()
    raw_path = write_raw_text("web", artifact.digest, "source.html", response.text)
    artifact.raw_path = raw_path
    result = convert_source(str(raw_path))
    if not result.get("ok"):
        raise RuntimeError("MarkItDown returned no markdown")
    artifact.title = result.get("title") or _title_from_value(value)
    artifact.markdown = result["markdown"]
    artifact.metadata["converter"] = "markitdown"
    return artifact


def fetch_wechat(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "wechat", category)
    raw_root = raw_dir("wechat", artifact.digest)
    result = opencli_weixin_download(value, raw_root)
    markdown = result.get("markdown") or ""
    if not markdown:
        raise RuntimeError("opencli returned no markdown for wechat article")
    artifact.raw_path = Path(result["saved_md"]) if result.get("saved_md") else None
    artifact.title = result.get("title") or "wechat article"
    artifact.markdown = markdown
    assets_dir = result.get("assets_dir")
    if assets_dir:
        artifact.assets_dir = Path(assets_dir)
    artifact.metadata.update(
        {
            "account": result.get("account"),
            "publish_time": result.get("publish_time"),
            "provider": "opencli",
        }
    )
    return artifact


def fetch_bilibili(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "bilibili", category)
    result = extract_bilibili(value)
    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "Bilibili extraction failed")
    raw_path = write_raw_text("bilibili", artifact.digest, "source.html", result.get("html") or "")
    artifact.raw_path = raw_path
    transcript_path = write_raw_text(
        "bilibili",
        artifact.digest,
        "transcript.json",
        json.dumps(
            {
                "source": (result.get("metadata") or {}).get("transcript_source"),
                "text": result.get("transcript") or "",
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    artifact.title = result.get("title") or "bilibili video"
    artifact.markdown = result.get("markdown") or ""
    artifact.metadata.update(dict(result.get("metadata") or {}))
    artifact.metadata["transcript_path"] = str(transcript_path)
    return artifact


def fetch_github(value: str, *, category: str) -> KnowledgeArtifact:
    artifact = _new_artifact(value, "github", category)
    result = extract_github(value)
    raw = result.get("raw") or {}
    write_raw_text(
        "github",
        artifact.digest,
        "metadata.json",
        json.dumps(raw.get("repo") or {}, ensure_ascii=False, indent=2),
    )
    readme_path = write_raw_text(
        "github",
        artifact.digest,
        "readme.md",
        raw.get("readme") or "",
    )
    artifact.raw_path = readme_path
    artifact.title = result.get("title") or "github repo"
    artifact.markdown = result.get("markdown") or ""
    artifact.metadata.update(dict(result.get("metadata") or {}))
    return artifact


_FETCHERS = {
    "markdown": fetch_markdown,
    "markitdown": fetch_markitdown,
    "youtube": fetch_youtube,
    "web": fetch_web,
    "wechat": fetch_wechat,
    "bilibili": fetch_bilibili,
    "github": fetch_github,
}


def fetch(value: str, *, category: str) -> KnowledgeArtifact:
    """Detect the source type, run the matching adapter, return a populated artifact."""
    category = validate_category(category)
    source_type = detect_source_type(value)
    artifact = _FETCHERS[source_type](value, category=category)
    _apply_sidecar_metadata(artifact, value)
    artifact.markdown = _normalize_spacing(artifact.markdown)
    return artifact


def _apply_sidecar_metadata(artifact: KnowledgeArtifact, value: str) -> None:
    """Seed provenance from a staged ``<stem>.meta.json`` sidecar, if present.

    The dashboard's radar "Ingest to wiki" staging writes source_url / published /
    author next to the staged HTML (structured data) instead of baking an English
    label block into the body. Best-effort: a missing / malformed sidecar is
    ignored, and an existing metadata key is never overwritten.
    """
    if _is_url(value):
        return
    sidecar = Path(value).expanduser().with_suffix(".meta.json")
    if not sidecar.is_file():
        return
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    for key in ("source_url", "published", "author"):
        val = data.get(key)
        if val and not artifact.metadata.get(key):
            artifact.metadata[key] = str(val)


def _normalize_spacing(markdown: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _title_from_value(value: str) -> str:
    path = Path(value)
    return path.stem if path.suffix else value.rstrip("/").rsplit("/", 1)[-1] or "knowledge source"


def _validate_public_web_url(value: str) -> None:
    parsed = urlparse(value)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        raise RuntimeError(f"unsupported web URL: {value}")
    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise RuntimeError(f"refusing private web URL host: {host}")
    try:
        addresses = {
            ipaddress.ip_address(info[4][0])
            for info in socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
        }
    except OSError as e:
        raise RuntimeError(f"could not resolve web URL host {host!r}: {e}") from e
    for address in addresses:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise RuntimeError(f"refusing private web URL host: {host} -> {address}")


def _get_public_web(client, value: str):
    current = value
    for _ in range(5):
        _validate_public_web_url(current)
        response = client.get(current, follow_redirects=False)
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        current = urljoin(str(response.url), location)
    raise RuntimeError(f"too many redirects for web URL: {value}")
