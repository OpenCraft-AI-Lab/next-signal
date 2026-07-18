## ADDED Requirements

### Requirement: Knowledge ingest workflow is declared in config

The single-item knowledge ingest workflow SHALL be declared by `configs/workflows/knowledge_ingest.yaml`. The config SHALL identify the Python factory, AgentOS exposure, agent tool exposure, and manual run function.

#### Scenario: workflow config exposes AgentOS workflow

- **WHEN** `paca.orchestrator.runnable_loader.load_workflows()` runs
- **THEN** it builds `paca.workflows.knowledge_ingest:build` for `knowledge_ingest` when the workflow is enabled and `expose.agent_os` is true

#### Scenario: workflow config exposes agent tool

- **WHEN** `paca.registry.available()` is called
- **THEN** `knowledge_ingest_workflow` is registered from the workflow config and resolves to a `WorkflowTools` toolkit

### Requirement: Pipeline state is carried by `KnowledgeArtifact`

The knowledge ingest workflow SHALL pass state between stages as a single `KnowledgeArtifact` dataclass instance under `src/paca/workflows/stages/knowledge_ingest/`.

The `KnowledgeArtifact` SHALL include source value, source type, digest, optional raw path, title, markdown, metadata, optional artifact edit, optional clean path, optional frontmatter, and optional ingest result.

#### Scenario: edit stage reads markdown from artifact

- **WHEN** the `edit` stage runs after `fetch`
- **THEN** it reads markdown from the `KnowledgeArtifact` returned by `fetch`

### Requirement: Workflow topology is fetch edit persist

The knowledge ingest `Workflow` SHALL declare these steps in order:

1. `fetch`
2. `edit`
3. `persist`

Each step SHALL be a thin adapter that unwraps `StepInput`, calls the corresponding stage function, and returns `StepOutput(content=artifact)`.

#### Scenario: workflow runs Bilibili input

- **WHEN** the workflow runs on a Bilibili URL with fake adapters in tests
- **THEN** the final step content is a `KnowledgeArtifact` with `source_type == "bilibili"` and persisted output metadata

### Requirement: Provider adapters stay under integrations

OpenCLI (WeChat) and Bilibili provider details SHALL live under `src/paca/integrations/knowledge/`. Workflow stages and tools SHALL call those adapters rather than embedding provider HTTP / CLI behavior.

#### Scenario: fetch wechat uses OpenCLI adapter

- **WHEN** `fetch_wechat` runs
- **THEN** it calls `paca.integrations.knowledge.opencli.opencli_weixin_download`

### Requirement: Workflow tool exposure is centralized

The workflow SHALL be exposed to agents through `paca.orchestrator.workflow_tools`, using the `expose.tool` section in workflow config. Domain packages SHALL NOT create separate workflow-tool wrapper modules for the same workflow.

#### Scenario: knowledge manager lists workflow tool

- **WHEN** `configs/agents/knowledge_manager.yaml` is loaded
- **THEN** it lists `knowledge_ingest_workflow` and does not list `knowledge_pipeline_workflow`

### Requirement: Manual run uses configured run function

The CLI schedule runner SHALL use `WorkflowConfig.extra.run_now` for manual workflow execution.

#### Scenario: weekly knowledge ingest runs manually

- **WHEN** `uv run paca schedule run-now weekly_knowledge_ingest` is invoked
- **THEN** the CLI resolves `knowledge_ingest` to `paca.workflows.knowledge_ingest:run`
