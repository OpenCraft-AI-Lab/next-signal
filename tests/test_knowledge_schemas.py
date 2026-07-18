from __future__ import annotations

import pytest
from pydantic import ValidationError

from paca.workflows.stages.knowledge_ingest.schemas import FrontmatterDraft, category_model


def test_frontmatter_normalizes_tags() -> None:
    draft = FrontmatterDraft(
        summary="a dense factual summary.",
        tags=["Alpha", "中文标签", "alpha", "beta tag"],
    )
    assert draft.tags == ["alpha", "beta-tag"]


def test_frontmatter_drops_cjk_and_caps_tags() -> None:
    draft = FrontmatterDraft(
        summary="s.",
        tags=["AI", "ai", "深度学习", "Visual Primitives", "t3", "t4", "t5", "t6"],
    )
    assert draft.tags == ["ai", "visual-primitives", "t3", "t4", "t5"]


def test_frontmatter_rejects_empty_summary() -> None:
    with pytest.raises(ValidationError, match="summary"):
        FrontmatterDraft(summary="   ", tags=["a"])


def test_frontmatter_rejects_no_valid_tags() -> None:
    with pytest.raises(ValidationError, match="tag"):
        FrontmatterDraft(summary="s.", tags=["中文", ""])


def test_frontmatter_rejects_invalid_freshness() -> None:
    with pytest.raises(ValidationError):
        FrontmatterDraft(summary="s.", tags=["a"], freshness="nonsense")


def test_frontmatter_freshness_empty_becomes_none() -> None:
    draft = FrontmatterDraft(summary="s.", tags=["a"], freshness="  ")
    assert draft.freshness is None


def test_frontmatter_to_artifact_edit() -> None:
    draft = FrontmatterDraft(summary="s.", tags=["a", "b"], freshness="stable")
    assert draft.to_artifact_edit() == {
        "summary": "s.",
        "tags": ["a", "b"],
        "freshness": "stable",
    }


def test_category_model_accepts_valid_paths() -> None:
    model = category_model(["knowledge/ai-ml", "investing/quant"])
    assert model(category="knowledge/ai-ml").category == "knowledge/ai-ml"
    assert model(category="temp-inbox").category == "temp-inbox"


def test_category_model_rejects_unknown_path() -> None:
    model = category_model(["knowledge/ai-ml"])
    with pytest.raises(ValidationError):
        model(category="made/up/path")
