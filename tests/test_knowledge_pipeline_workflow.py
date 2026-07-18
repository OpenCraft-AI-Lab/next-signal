from __future__ import annotations

import paca.workflows.knowledge_ingest as knowledge_ingest


def test_knowledge_ingest_workflow_build_is_centralized() -> None:
    assert knowledge_ingest.build().id == "knowledge_ingest"
