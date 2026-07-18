## 1. Central workflow declaration

- [x] 1.1 Add `configs/workflows/knowledge_ingest.yaml` with `factory: paca.workflows.knowledge_ingest:build`.
- [x] 1.2 Configure `expose.agent_os: true`.
- [x] 1.3 Configure `expose.tool.name: knowledge_ingest_workflow`.
- [x] 1.4 Configure `extra.run_now: paca.workflows.knowledge_ingest:run` for scheduler / CLI manual runs.

## 2. Workflow implementation

- [x] 2.1 Move the workflow factory to `src/paca/workflows/knowledge_ingest.py`.
- [x] 2.2 Keep the workflow steps as `fetch`, `edit`, and `persist`.
- [x] 2.3 Keep per-step retry / fail-loud behavior in the `Step` definitions.
- [x] 2.4 Keep weekly wiki re-index in the same workflow module.

## 3. Workflow-private stages

- [x] 3.1 Move `KnowledgeArtifact` to `src/paca/workflows/stages/knowledge_ingest/artifact.py`.
- [x] 3.2 Move source classification, raw storage, fetch, artifact editing, and persistence into `src/paca/workflows/stages/knowledge_ingest/`.
- [x] 3.3 Keep provider details out of stage code except through `integrations/`.

## 4. Agent-facing surfaces

- [x] 4.1 Expose the workflow as `knowledge_ingest_workflow` through `paca.orchestrator.workflow_tools`.
- [x] 4.2 Keep `search_knowledge` in `src/paca/tools/knowledge/search.py`.
- [x] 4.3 Remove the old `knowledge_pipeline_workflow` compatibility alias.

## 5. Verification

- [x] 5.1 Run `uv run pytest -q`.
- [x] 5.2 Run touched-file `uv run ruff check ...`.
- [x] 5.3 Run `uv run paca list` and confirm workflows are listed from config.
- [x] 5.4 Smoke test a real external URL end to end when OMLX, GBrain, and network credentials are available.
