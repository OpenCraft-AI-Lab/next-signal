## RENAMED Requirements

- FROM: `### Requirement: `paca knowledge ingest` accepts URLs and files`
- TO: `### Requirement: `next-signal knowledge ingest` accepts URLs and files`

## MODIFIED Requirements

### Requirement: `next-signal knowledge ingest` accepts URLs and files

The CLI command `next-signal knowledge ingest <url|file>` SHALL detect the source type (microblog article, YouTube, Bilibili, PDF, Office, HTML, image, plain markdown) and route to the matching adapter. The command SHALL accept an optional `--category <path>` flag that pins the destination wiki folder, and an optional `--progress` flag that emits one JSON event per pipeline step to stdout. With both flags absent the command behaves as before (automatic classification, single result-JSON line on stdout).

#### Scenario: WeChat article saved

- **WHEN** `next-signal knowledge ingest https://mp.weixin.qq.com/s/<id>` is run
- **THEN** the OpenCLI adapter downloads the article + images to the raw store, rewrites image references to local relative paths, and emits clean markdown

#### Scenario: YouTube video saved

- **WHEN** the input URL is a YouTube link
- **THEN** the MarkItDown adapter writes the converted markdown and a raw conversion JSON

#### Scenario: category pinned via flag

- **WHEN** `next-signal knowledge ingest <url> --category knowledge/ai-ml` is run with a path present in the taxonomy
- **THEN** the artifact is written under that folder and the LLM classification step is skipped

#### Scenario: unknown category rejected

- **WHEN** `next-signal knowledge ingest <url> --category not/a/real/path` is run
- **THEN** the command fails loud with a non-zero exit before performing the ingest work

#### Scenario: progress events streamed

- **WHEN** `next-signal knowledge ingest <url> --progress` is run
- **THEN** stdout contains one JSON event line per pipeline step as each step starts and completes, followed by the final result JSON as the last line, with all lines forming valid JSONL

### Requirement: Two-tree artifact layout

Clean markdown artifacts SHALL be written under `<WIKI_DIR>/<category>/`, and originals under `<WIKI_RAW_DIR>/`. Both roots SHALL be resolved lazily from the required `WIKI_DIR` / `WIKI_RAW_DIR` environment variables (`src/next_signal/core/paths.py`); there is no hardcoded default, and reading either path with the variable unset SHALL raise a loud `RuntimeError`.

#### Scenario: paths separated by purpose

- **WHEN** any source is saved
- **THEN** the wiki tree contains only LLM-friendly markdown; the raw tree contains the original file (HTML, PDF, audio, etc.)

#### Scenario: wiki path env var unset

- **WHEN** `WIKI_DIR` (or `WIKI_RAW_DIR`) is not set and code attempts to resolve the wiki root
- **THEN** a `RuntimeError` is raised instead of falling back to a default path

### Requirement: GitHub repo URLs are a first-class source type

`next-signal knowledge ingest` SHALL detect `https://github.com/<owner>/<repo>` as `source_type == "github"` and route it to a GitHub-specific adapter that collects signal beyond the rendered README. Non-root GitHub URLs (paths beyond `/<owner>/<repo>`, including `/blob`, `/tree`, `/issues`, `/pull`, gist, and user-only pages) SHALL raise a loud error rather than falling back to the generic web adapter.

#### Scenario: root repo URL is recognized

- **WHEN** `next-signal knowledge ingest https://github.com/<owner>/<repo>` is run (with or without a trailing slash)
- **THEN** detection returns `source_type == "github"` and the github fetcher runs

#### Scenario: subpath URL is rejected loud

- **WHEN** the input is `https://github.com/<owner>/<repo>/blob/...`, `/tree/...`, `/issues/...`, `/pull/...`, a single-segment user URL, or any other non-root GitHub path
- **THEN** detection raises `RuntimeError` instead of routing to the generic web adapter

### Requirement: Knowledge ingest workflow is declared in config

The single-item knowledge ingest workflow SHALL be declared by `configs/workflows/knowledge_ingest.yaml`. The config SHALL identify the Python factory, AgentOS exposure, agent tool exposure, and manual run function.

#### Scenario: workflow config exposes AgentOS workflow

- **WHEN** `next_signal.orchestrator.runnable_loader.load_workflows()` runs
- **THEN** it builds `next_signal.workflows.knowledge_ingest:build` for `knowledge_ingest` when the workflow is enabled and `expose.agent_os` is true

#### Scenario: workflow config exposes agent tool

- **WHEN** `next_signal.registry.available()` is called
- **THEN** `knowledge_ingest_workflow` is registered from the workflow config and resolves to a `WorkflowTools` toolkit

### Requirement: Pipeline state is carried by `KnowledgeArtifact`

The knowledge ingest workflow SHALL pass state between stages as a single `KnowledgeArtifact` dataclass instance under `src/next_signal/workflows/stages/knowledge_ingest/`.

The `KnowledgeArtifact` SHALL include source value, source type, digest, optional raw path, title, markdown, metadata, optional artifact edit, optional clean path, optional frontmatter, and optional ingest result.

#### Scenario: edit stage reads markdown from artifact

- **WHEN** the `edit` stage runs after `fetch`
- **THEN** it reads markdown from the `KnowledgeArtifact` returned by `fetch`

### Requirement: Provider adapters stay under integrations

OpenCLI (WeChat) and Bilibili provider details SHALL live under `src/next_signal/integrations/knowledge/`. Workflow stages and tools SHALL call those adapters rather than embedding provider HTTP / CLI behavior.

#### Scenario: fetch wechat uses OpenCLI adapter

- **WHEN** `fetch_wechat` runs
- **THEN** it calls `next_signal.integrations.knowledge.opencli.opencli_weixin_download`

### Requirement: Workflow tool exposure is centralized

The workflow SHALL be exposed to agents through `next_signal.orchestrator.workflow_tools`, using the `expose.tool` section in workflow config. Domain packages SHALL NOT create separate workflow-tool wrapper modules for the same workflow.

#### Scenario: an agent lists the workflow tool

- **WHEN** an agent YAML declares `tools: [knowledge_ingest_workflow]`
- **THEN** the registry resolves it to the workflow's `WorkflowTools` toolkit and no separate `knowledge_pipeline_workflow` wrapper exists

Note: no agent in this repo currently ships with `knowledge_ingest_workflow` in its `tools:` list (there is no `knowledge_manager` agent) — the mechanism above is exercised by `next-signal run-workflow knowledge_ingest` and the dashboard's re-index action, not by an agent-initiated tool call, as of this repo.

### Requirement: Manual run uses configured run function

The `next-signal run-workflow` CLI command SHALL use `WorkflowConfig.extra.run_now` for manual workflow execution.

#### Scenario: knowledge ingest runs manually

- **WHEN** `uv run next-signal run-workflow knowledge_ingest` is invoked
- **THEN** the CLI resolves `knowledge_ingest` to `next_signal.workflows.knowledge_ingest:run` and calls it
