from __future__ import annotations

from agno.tools.workflow import WorkflowTools

from paca.registry import resolve_tools


def test_knowledge_ingest_tool_is_serialization_safe() -> None:
    """`knowledge_ingest_workflow` is a plain function tool, not `WorkflowTools`.

    `WorkflowTools.run_workflow` does `json.dumps(result.to_dict())` on the raw
    workflow output, which fails on the pipeline's `KnowledgeArtifact` step
    content (Path fields) — the agent then mis-reports a successful ingest as a
    failure. The function tool returns `ingest_one`'s already JSON-safe dict.
    """
    (tool,) = resolve_tools(["knowledge_ingest_workflow"])
    assert not isinstance(tool, WorkflowTools)
    assert getattr(tool, "name", None) == "knowledge_ingest_workflow"
