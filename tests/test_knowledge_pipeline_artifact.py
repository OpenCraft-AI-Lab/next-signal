from __future__ import annotations

import json
from pathlib import Path

from paca.workflows.stages.knowledge_ingest import KnowledgeArtifact


def _base(**overrides) -> KnowledgeArtifact:
    defaults = dict(
        value="https://example.com/x",
        source_type="web",
        digest="abc123",
        created_at="2026-05-15T00:00:00+00:00",
        category="knowledge",
    )
    defaults.update(overrides)
    return KnowledgeArtifact(**defaults)


def test_required_fields_and_defaults() -> None:
    a = _base()
    assert a.value == "https://example.com/x"
    assert a.title == ""
    assert a.markdown == ""
    assert a.raw_path is None
    assert a.metadata == {}
    assert a.artifact_edit is None
    assert a.clean_path is None
    assert a.frontmatter is None
    assert a.ingest_result is None


def test_to_jsonable_round_trips_through_json() -> None:
    a = _base(
        title="t",
        markdown="# hi",
        raw_path=Path("/tmp/raw"),
        metadata={"k": "v"},
        artifact_edit={"summary": "s", "tags": ["a"], "freshness": "stable"},
        clean_path=Path("/tmp/clean.md"),
        frontmatter={"title": "t"},
        ingest_result={"ok": True},
    )
    payload = a.to_jsonable()
    assert payload["raw_path"] == str(Path("/tmp/raw"))
    assert payload["clean_path"] == str(Path("/tmp/clean.md"))
    assert payload["artifact_edit"]["summary"] == "s"
    text = json.dumps(payload)
    assert "# hi" in text


def test_to_jsonable_passthroughs_for_none_fields() -> None:
    a = _base()
    payload = a.to_jsonable()
    assert payload["raw_path"] is None
    assert payload["clean_path"] is None
    assert payload["artifact_edit"] is None
    assert payload["frontmatter"] is None
    assert payload["ingest_result"] is None
    assert payload["metadata"] == {}
