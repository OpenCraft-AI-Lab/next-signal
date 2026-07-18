# Design: centralized knowledge ingest workflow

## Current shape

Knowledge ingest is a single centralized workflow:

```text
configs/workflows/knowledge_ingest.yaml
        |
        v
src/paca/workflows/knowledge_ingest.py
        |
        v
src/paca/workflows/stages/knowledge_ingest/
  artifact.py
  classify.py
  raw_store.py
  fetch.py
  artifact_editor.py
  persist.py
```

The workflow topology is intentionally small:

```text
fetch -> edit -> persist
```

`fetch` handles source-type classification and adapter calls, `edit` calls the DB-free
`knowledge_artifact_editor` agent, and `persist` writes the wiki artifact and optionally imports it into GBrain.

## Boundaries

- Workflow topology and retry policy live in `src/paca/workflows/knowledge_ingest.py`.
- Workflow-private state and stage helpers live in `src/paca/workflows/stages/knowledge_ingest/`.
- The agent-facing knowledge tool `search_knowledge` lives in `src/paca/tools/knowledge/`.
- Provider adapters live in `src/paca/integrations/knowledge/`.
- GBrain remains horizontal infrastructure in `src/paca/integrations/gbrain.py` and `src/paca/tools/gbrain.py`.

Do not recreate a domain-local `workflow_tools.py`. Workflow tool exposure is centralized through `paca.orchestrator.workflow_tools` and driven by `configs/workflows/<name>.yaml`.

## Exposure

`configs/workflows/knowledge_ingest.yaml` controls three surfaces:

- `factory: paca.workflows.knowledge_ingest:build` builds the workflow.
- `expose.agent_os: true` registers it with AgentOS.
- `expose.tool.name: knowledge_ingest_workflow` registers a `WorkflowTools` toolkit for agents.
- `extra.run_now: paca.workflows.knowledge_ingest:run` lets scheduler / CLI run the weekly re-index path.

This keeps "workflow as AgentOS runnable" and "workflow as agent tool" as two exposures of the same workflow, not two implementations.

## Trade-offs

- The stage package is under `workflows/stages/` rather than `tools/knowledge/` because these helpers are private to the ingest workflow. If another workflow needs one of them, promote that behavior to `tools/` or `integrations/`.
- The workflow uses a single `fetch` step rather than a Router with one Step per source type. That keeps the current implementation smaller while preserving source-type unit tests in the stage layer.
- The workflow has no legacy `knowledge_pipeline_workflow` alias. Agents should use `knowledge_ingest_workflow`.

## Verification

- Unit tests cover stage functions, adapters, persistence, workflow execution, and registry exposure.
- `uv run paca list` must show `knowledge_ingest` under workflows.
- Real URL smoke tests require network, OMLX, and GBrain; keep them manual or marked integration.
