## Why

The knowledge ingest path is now a centralized `agno` workflow rather than a module-local helper. Future work needs the OpenSpec change to match the current structure so follow-on tasks keep using the current `knowledge_ingest` workflow shape.

## What Changes

- Treat `configs/workflows/knowledge_ingest.yaml` as the workflow declaration and exposure source.
- Keep the implementation in `src/paca/workflows/knowledge_ingest.py`.
- Keep workflow-private pipeline state and stages in `src/paca/workflows/stages/knowledge_ingest/`.
- Expose the agent-facing workflow tool through `paca.orchestrator.workflow_tools`, not a domain-local `workflow_tools.py` wrapper.
- Keep `search_knowledge` as the knowledge agent-facing tool in `src/paca/tools/knowledge/`.
- Keep OpenCLI (WeChat) and Bilibili provider adapters in `src/paca/integrations/knowledge/`.

## Capabilities

### Modified Capabilities

- `knowledge-pipeline`: adds config-driven workflow declaration, `KnowledgeArtifact` pipeline state, the fetch -> edit -> persist topology, and centralized agent-tool exposure.
- `core-agent-os`: workflows are loaded from `configs/workflows/*.yaml` by the centralized runnable loader.
- `core-tools`: configured workflow tool exposure registers `WorkflowTools` under stable tool names.

## Impact

- Code:
  - `src/paca/workflows/knowledge_ingest.py`
  - `src/paca/workflows/stages/knowledge_ingest/`
  - `src/paca/orchestrator/workflow_tools.py`
  - `src/paca/tools/knowledge/`
  - `src/paca/integrations/knowledge/`
- Config:
  - `configs/workflows/knowledge_ingest.yaml`
  - `configs/agents/knowledge_manager.yaml`
- Tests:
  - workflow, stage, registry, CLI, and adapter tests stay under `tests/`.
- No dependency changes.
