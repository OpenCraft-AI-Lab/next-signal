"""Pipeline state object that flows through the knowledge ingest steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


def validate_category(category: str) -> str:
    """Return a safe wiki-relative category or raise."""
    value = category.strip().strip("/")
    if not value or ".." in value or value.startswith(("/", "~")):
        raise RuntimeError(f"invalid knowledge category: {category}")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
        raise RuntimeError(f"invalid knowledge category: {category}")
    return value


@dataclass
class KnowledgeArtifact:
    """State carried through the knowledge ingest pipeline.

    The fetch / edit / persist steps populate fields incrementally: fetch sets
    the source-side fields, edit replaces `markdown` and sets `artifact_edit`,
    persist sets `clean_path` / `frontmatter` / `ingest_result`.
    """

    value: str
    source_type: str
    digest: str
    created_at: str
    category: str

    title: str = ""
    # The original, pre-LLM source title, captured before the frontmatter agent
    # replaces `title` with a localized one. Preserved in frontmatter and used to
    # derive the wiki slug so the same source keeps a stable identity across locales.
    source_title: str | None = None
    markdown: str = ""
    raw_path: Path | None = None
    assets_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    artifact_edit: dict[str, Any] | None = None

    clean_path: Path | None = None
    frontmatter: dict[str, Any] | None = None
    ingest_result: dict[str, Any] | None = None

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the artifact for `StepOutput.content`."""
        return {
            "value": self.value,
            "source_type": self.source_type,
            "digest": self.digest,
            "created_at": self.created_at,
            "category": self.category,
            "title": self.title,
            "source_title": self.source_title,
            "markdown": self.markdown,
            "raw_path": str(self.raw_path) if self.raw_path is not None else None,
            "assets_dir": str(self.assets_dir) if self.assets_dir is not None else None,
            "metadata": dict(self.metadata),
            "artifact_edit": (
                dict(self.artifact_edit) if self.artifact_edit is not None else None
            ),
            "clean_path": str(self.clean_path) if self.clean_path is not None else None,
            "frontmatter": dict(self.frontmatter) if self.frontmatter is not None else None,
            "ingest_result": dict(self.ingest_result) if self.ingest_result is not None else None,
        }
