from __future__ import annotations

import json

import paca.workflows.stages.knowledge_ingest.classify as classify_mod
from paca.workflows.stages.knowledge_ingest import KnowledgeArtifact
from paca.workflows.stages.knowledge_ingest.classify import classify_category


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


def _stub_classifier(monkeypatch, payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

    class FakeAgent:
        def run(self, agent_input, **kwargs):
            return _FakeResponse(text)

    monkeypatch.setattr(classify_mod, "build_from_name", lambda name: FakeAgent())


def _artifact() -> KnowledgeArtifact:
    return KnowledgeArtifact(
        value="https://example.com/x",
        source_type="web",
        digest="abc123",
        created_at="2026-05-15T00:00:00+00:00",
        category="temp-inbox",
        title="An intro to transformer attention",
        artifact_edit={
            "summary": "How self-attention works in transformer models.",
            "tags": ["transformers", "attention"],
            "freshness": "stable",
        },
    )


def test_classify_sets_a_taxonomy_category(monkeypatch) -> None:
    _stub_classifier(monkeypatch, {"category": "knowledge/ai-ml"})
    assert classify_category(_artifact()).category == "knowledge/ai-ml"


def test_classify_falls_back_to_temp_inbox_on_invalid_path(monkeypatch) -> None:
    _stub_classifier(monkeypatch, {"category": "not/a/real/category"})
    assert classify_category(_artifact()).category == "temp-inbox"


def test_classify_falls_back_to_temp_inbox_on_unparseable_output(monkeypatch) -> None:
    _stub_classifier(monkeypatch, "not json at all")
    assert classify_category(_artifact()).category == "temp-inbox"


def test_classify_falls_back_to_temp_inbox_on_agent_error(monkeypatch) -> None:
    class BoomAgent:
        def run(self, agent_input, **kwargs):
            raise RuntimeError("classifier offline")

    monkeypatch.setattr(classify_mod, "build_from_name", lambda name: BoomAgent())
    assert classify_category(_artifact()).category == "temp-inbox"
