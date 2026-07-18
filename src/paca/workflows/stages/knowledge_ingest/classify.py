"""Knowledge input routing: deterministic source-type detection and LLM category
classification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from paca.agents.loader import build_from_name
from paca.agents.structured import run_structured
from paca.workflows.stages.knowledge_ingest.artifact import KnowledgeArtifact
from paca.workflows.stages.knowledge_ingest.schemas import category_model
from paca.workflows.stages.knowledge_ingest.taxonomy import category_paths, load_taxonomy

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tiff", ".bmp"}
_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_MARKITDOWN_SUFFIXES = {
    ".csv",
    ".docx",
    ".epub",
    ".html",
    ".htm",
    ".json",
    ".pdf",
    ".pptx",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
    *_IMAGE_SUFFIXES,
}


def detect_source_type(value: str) -> str:
    """Return the deterministic adapter route for a URL or local file."""
    source = value.strip()
    parsed = urlparse(source)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if parsed.scheme in {"http", "https"}:
        if host == "mp.weixin.qq.com":
            return "wechat"
        if host in {"youtube.com", "m.youtube.com", "youtu.be"}:
            return "youtube"
        if host.endswith("bilibili.com") or host == "b23.tv":
            return "bilibili"
        if host == "github.com":
            # Only the repo root /<owner>/<repo>[/] saves a repo artifact;
            # /blob, /tree, /issues, /pull, gists, user pages, etc. are not
            # supported by the github adapter and must raise loud rather than
            # silently falling back to the generic web fetcher.
            segments = [s for s in parsed.path.split("/") if s]
            if len(segments) == 2:
                return "github"
            raise RuntimeError(
                f"unsupported github URL: {value} — only repo root /<owner>/<repo> is supported"
            )
        return "web"

    suffix = Path(source).expanduser().suffix.lower()
    if suffix in _MARKDOWN_SUFFIXES:
        return "markdown"
    if suffix in _MARKITDOWN_SUFFIXES:
        return "markitdown"
    raise RuntimeError(f"unsupported knowledge input: {value}")


_FALLBACK_CATEGORY = "temp-inbox"


def classify_category(artifact: KnowledgeArtifact) -> KnowledgeArtifact:
    """Set `artifact.category` via the knowledge_classifier agent."""
    artifact.category = _pick_category(artifact)
    return artifact


def _pick_category(artifact: KnowledgeArtifact) -> str:
    taxonomy = load_taxonomy()
    try:
        agent = build_from_name("knowledge_classifier")
        schema = category_model(category_paths(taxonomy))
        result = run_structured(agent, _classifier_input(artifact, taxonomy), schema)
        return result.category
    except Exception:  # noqa: BLE001 — best-effort; temp-inbox is the designed fallback
        return _FALLBACK_CATEGORY


def _classifier_input(artifact: KnowledgeArtifact, taxonomy: dict[str, Any]) -> str:
    edit = artifact.artifact_edit or {}
    return json.dumps(
        {
            "title": artifact.title,
            "summary": edit.get("summary") or "",
            "tags": edit.get("tags") or [],
            "source_type": artifact.source_type,
            "categories": [
                {"path": entry["path"], "scope": entry["scope"]}
                for entry in taxonomy["categories"]
            ],
        },
        ensure_ascii=False,
    )
