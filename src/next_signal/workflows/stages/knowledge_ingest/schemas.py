"""Pydantic schemas for the knowledge-ingest agents' structured JSON output.

These are the single source of truth: agno serializes them into a json_schema
`response_format` (OMLX constrains the model's tokens to it) and validates the
result back. The field validators carry the normalization and checks that the
hand-rolled `validate_*` helpers used to do.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, create_model, field_validator

_CJK_RE = re.compile("[㐀-鿿]")
_TAG_RE = re.compile(r"[a-z0-9][a-z0-9._+-]*")

Freshness = Literal["permanent", "stable", "evolving", "ephemeral"]


def _normalize_tags(value: Any) -> list[str]:
    """Lowercase English-only tags: drop CJK / malformed, dedupe, cap at 5."""
    items = value if isinstance(value, list) else []
    tags: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        tag = re.sub(r"\s+", "-", text.lower().lstrip("#")).strip("-_.+")
        if not tag or _CJK_RE.search(tag) or not _TAG_RE.fullmatch(tag):
            continue
        if tag not in tags:
            tags.append(tag)
    return tags[:5]


class FrontmatterDraft(BaseModel):
    """Output contract for the knowledge_frontmatter agent."""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    summary: str
    tags: list[str]
    freshness: Freshness | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("summary", mode="before")
    @classmethod
    def _clean_summary(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("summary must not be empty")
        return text

    @field_validator("tags", mode="before")
    @classmethod
    def _clean_tags(cls, value: Any) -> list[str]:
        tags = _normalize_tags(value)
        if not tags:
            raise ValueError("at least one English tag is required")
        return tags

    @field_validator("freshness", mode="before")
    @classmethod
    def _clean_freshness(cls, value: Any) -> str | None:
        if value is None or not str(value).strip():
            return None
        return str(value).strip().lower()

    def to_artifact_edit(self) -> dict[str, Any]:
        """The dict shape `persist.py` reads off `artifact.artifact_edit`."""
        return {
            "summary": self.summary,
            "tags": self.tags,
            "freshness": self.freshness,
        }


def category_model(valid_paths: list[str]) -> type[BaseModel]:
    """Build the knowledge_classifier output schema for the current taxonomy.

    `category` is a Literal of the taxonomy paths plus the `temp-inbox` fallback,
    so the json_schema enum lets OMLX hard-constrain the classifier's choice.
    """
    choices = tuple(valid_paths) + ("temp-inbox",)
    return create_model("CategoryChoice", category=(Literal[choices], ...))
