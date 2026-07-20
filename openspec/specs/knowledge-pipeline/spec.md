# knowledge-pipeline

Unified knowledge artifact pipeline: a URL or local file becomes (1) a clean markdown artifact in the wiki, (2) a raw archive copy, and (3) optionally an indexed entry in GBrain.

## Purpose

Every saved item produces durable, human-readable markdown — independent of whether the downstream RAG / vector store is healthy. A failure in GBrain ingest must never lose the artifact.
## Requirements
### Requirement: `paca knowledge ingest` accepts URLs and files

The CLI command `paca knowledge ingest <url|file>` SHALL detect the source type (microblog article, YouTube, Bilibili, PDF, Office, HTML, image, plain markdown) and route to the matching adapter. The command SHALL accept an optional `--category <path>` flag that pins the destination wiki folder, and an optional `--progress` flag that emits one JSON event per pipeline step to stdout. With both flags absent the command behaves as before (automatic classification, single result-JSON line on stdout).

#### Scenario: WeChat article saved

- **WHEN** `paca knowledge ingest https://mp.weixin.qq.com/s/<id>` is run
- **THEN** the OpenCLI adapter downloads the article + images to the raw store, rewrites image references to local relative paths, and emits clean markdown

#### Scenario: YouTube video saved

- **WHEN** the input URL is a YouTube link
- **THEN** the MarkItDown adapter writes the converted markdown and a raw conversion JSON

#### Scenario: category pinned via flag

- **WHEN** `paca knowledge ingest <url> --category knowledge/ai-ml` is run with a path present in the taxonomy
- **THEN** the artifact is written under that folder and the LLM classification step is skipped

#### Scenario: unknown category rejected

- **WHEN** `paca knowledge ingest <url> --category not/a/real/path` is run
- **THEN** the command fails loud with a non-zero exit before performing the ingest work

#### Scenario: progress events streamed

- **WHEN** `paca knowledge ingest <url> --progress` is run
- **THEN** stdout contains one JSON event line per pipeline step as each step starts and completes, followed by the final result JSON as the last line, with all lines forming valid JSONL

### Requirement: Two-tree artifact layout

Clean markdown artifacts SHALL be written under `<PACA_WIKI_DIR>/<category>/`, and originals under `<PACA_WIKI_RAW_DIR>/`. Both roots SHALL be resolved lazily from the required `PACA_WIKI_DIR` / `PACA_WIKI_RAW_DIR` environment variables (`src/paca/core/paths.py`); there is no hardcoded default, and reading either path with the variable unset SHALL raise a loud `RuntimeError`.

#### Scenario: paths separated by purpose

- **WHEN** any source is saved
- **THEN** the wiki tree contains only LLM-friendly markdown; the raw tree contains the original file (HTML, PDF, audio, etc.)

#### Scenario: wiki path env var unset

- **WHEN** `PACA_WIKI_DIR` (or `PACA_WIKI_RAW_DIR`) is not set and code attempts to resolve the wiki root
- **THEN** a `RuntimeError` is raised instead of falling back to a default path

### Requirement: GBrain ingest failure does not lose artifacts

After writing artifacts, the ingest workflow MAY call `gbrain_ingest(path)`. If the ingest call fails, the artifact files SHALL remain on disk and the workflow SHALL raise a loud error.

#### Scenario: GBrain CLI offline

- **WHEN** the GBrain CLI is unreachable during save
- **THEN** the markdown and raw files are still present on disk
- **AND** the workflow fails instead of advancing as a successful ingest

### Requirement: Knowledge ingest uses agent-led orchestration

The single-item knowledge ingest path SHALL be coordinated by an Agno workflow that calls deterministic workflow stages or tools for fetch, artifact editing, validation, wiki write, and optional GBrain ingest while preserving the existing JSON result shape.

#### Scenario: ingest result remains compatible

- **WHEN** the ingest workflow completes successfully for a supported input
- **THEN** the result includes `ok`, `source_type`, `category`, `markdown_path`, `raw_path`, `frontmatter`, and optional `ingest` fields with the same meaning as before

#### Scenario: an agent uses the ingest workflow tool

- **WHEN** an agent configured with the `knowledge_ingest_workflow` tool handles a request to ingest a URL or staged file
- **THEN** it uses `knowledge_ingest_workflow` instead of calling low-level `gbrain_ingest` directly

### Requirement: Artifact editing is split into a clean pass and a frontmatter pass

The pipeline SHALL transform a fetched source packet into cleaned markdown and frontmatter draft fields (`title`, `summary`, `tags`, `freshness`) via two separate agent passes rather than one combined call: `clean_body` (the `clean` step) runs the `knowledge_artifact_editor` agent (or `knowledge_github_cleaner` for github sources) and returns plain cleaned markdown text with no schema; `write_frontmatter` (the `enrich` step) separately runs `knowledge_frontmatter` (or `knowledge_github_summary` for github sources) under the `FrontmatterDraft` pydantic schema via `run_structured`. This split exists because a single combined pass would intermittently have a local model drop a field (e.g. an empty `summary`) — splitting keeps each call's output small and focused.

#### Scenario: orchestrator avoids full-body editing

- **WHEN** a fetched markdown packet is ready for content processing
- **THEN** the orchestrator passes the packet to `clean_body` and `write_frontmatter` in turn and does not generate cleaned markdown or frontmatter itself

#### Scenario: clean pass returns plain markdown, not structured output

- **WHEN** `clean_body` runs
- **THEN** it returns plain cleaned markdown text (no schema); only `write_frontmatter`'s output is parsed as structured data (`FrontmatterDraft`)

### Requirement: LLM artifact edit and frontmatter enrichment fail loud

`clean_body` and `write_frontmatter` SHALL together populate cleaned markdown plus `summary`, `tags`, `freshness` (`permanent` / `stable` / `evolving` / `ephemeral`), and source metadata across their two passes. If either LLM call or `write_frontmatter`'s structured output validation fails, the workflow SHALL fail loud rather than writing deterministic fallback content.

#### Scenario: transcript summary is rejected

- **WHEN** the source contains a transcript and the edited markdown removes the transcript section or compresses the body below the configured retention threshold
- **THEN** validation fails and the artifact is not written

#### Scenario: invalid frontmatter is rejected

- **WHEN** the artifact editor returns empty summary text, invalid freshness, or tags that do not match the required lowercase English tag format
- **THEN** validation fails and the artifact is not written

#### Scenario: editor call unavailable

- **WHEN** the artifact editor agent cannot complete the required edit
- **THEN** the save operation raises a loud failure and no clean wiki artifact is written

#### Scenario: clean-step retry is a blind step re-run

- **WHEN** the `clean` step (`max_retries=1`) fails validation (e.g. the retention guard trips)
- **THEN** the workflow step re-runs `clean_body` from the same input rather than sending validation feedback back to the agent; a second failure raises loud

#### Scenario: frontmatter-step retry uses schema-validation feedback

- **WHEN** `write_frontmatter`'s `run_structured` call produces output that fails `FrontmatterDraft` validation
- **THEN** the agent is re-prompted with the exact validation error and retried (up to `run_structured`'s `max_repairs`); a still-invalid result raises `RuntimeError` instead of creating fallback frontmatter

#### Scenario: related links empty when no matches

- **WHEN** the post-ingest hybrid `gbrain_query` against the article's title + summary returns no other-page results
- **THEN** the article is written without a `## Related` marker block; refresh cycles re-add one if the brain later finds neighbors

### Requirement: Direct ingest and re-index share GBrain identity

Direct single-input ingest and wiki re-index SHALL ingest markdown files under the same GBrain-safe slug derived from the wiki-relative markdown path.

#### Scenario: direct ingest matches weekly re-index slug

- **WHEN** direct ingest writes `knowledge/example.md`
- **THEN** GBrain ingest uses the same normalized slug that wiki re-index would use for the same file

### Requirement: Brain-driven Related section

After a successful GBrain ingest the pipeline SHALL append a marker-fenced `## Related` block to the wiki article containing `[[wikilink]]` references to the top hybrid-query neighbors. The weekly sync workflow SHALL refresh the marker block in every wiki article so neighbors stay current as the brain grows.

#### Scenario: ingest writes Related block on success

- **WHEN** `gbrain_ingest` returns ok and `gbrain_query(title + summary)` returns one or more other-page slugs
- **THEN** the wiki article has a single `<!-- gbrain:related ... -->` marker block at the bottom listing up to 8 resolved `[[wiki/path/Note]]` entries

#### Scenario: weekly sync refreshes every article

- **WHEN** the weekly sync workflow runs
- **THEN** it re-ingests changed files into GBrain AND re-queries the brain for every article with a parseable frontmatter, rewriting each marker block in place

#### Scenario: refresh is idempotent

- **WHEN** the refresh runs twice with no brain change in between
- **THEN** the second run does not modify any wiki file

### Requirement: GitHub repo URLs are a first-class source type

`paca knowledge ingest` SHALL detect `https://github.com/<owner>/<repo>` as `source_type == "github"` and route it to a GitHub-specific adapter that collects signal beyond the rendered README. Non-root GitHub URLs (paths beyond `/<owner>/<repo>`, including `/blob`, `/tree`, `/issues`, `/pull`, gist, and user-only pages) SHALL raise a loud error rather than falling back to the generic web adapter.

#### Scenario: root repo URL is recognized

- **WHEN** `paca knowledge ingest https://github.com/<owner>/<repo>` is run (with or without a trailing slash)
- **THEN** detection returns `source_type == "github"` and the github fetcher runs

#### Scenario: subpath URL is rejected loud

- **WHEN** the input is `https://github.com/<owner>/<repo>/blob/...`, `/tree/...`, `/issues/...`, `/pull/...`, a single-segment user URL, or any other non-root GitHub path
- **THEN** detection raises `RuntimeError` instead of routing to the generic web adapter

### Requirement: GitHub adapter assembles deep-signal markdown

The github fetcher SHALL produce a clean markdown packet with sections covering: repo metadata (description, license, language, stars, forks, open issues, topics, default branch, timestamps), project layout (top-level directory listing), recent releases (up to 3), the first matching top-level manifest file (`pyproject.toml`, `package.json`, `Cargo.toml`, or `go.mod`), recent commit subjects (up to 10), activity (contributors count, language breakdown), and the README body. Non-README signal sections that fail to fetch SHALL be silently omitted from the packet; failure to obtain the README SHALL raise a loud error.

#### Scenario: README missing causes loud failure

- **WHEN** the repo has no fetchable README
- **THEN** the fetcher raises an error and no artifact is written

#### Scenario: optional section failure does not abort

- **WHEN** the releases or manifest endpoint fails or returns 404
- **THEN** the packet omits that section and the ingest still succeeds with the README plus the other sections that did fetch

### Requirement: GitHub adapter authenticates only when a token is configured

The github fetcher SHALL read `GITHUB_TOKEN` at call time and send authenticated requests when it is set; when unset, it SHALL fall back to anonymous GitHub REST access and not require any environment configuration.

#### Scenario: token absent

- **WHEN** `GITHUB_TOKEN` is not set and the input is a public repo
- **THEN** the fetcher completes successfully using anonymous GitHub REST access

#### Scenario: token present

- **WHEN** `GITHUB_TOKEN` is set
- **THEN** the fetcher sends an `Authorization: Bearer <token>` header on each request

### Requirement: GitHub artifacts use a source-specific body cleaner

For `source_type == "github"` the `clean_body` step SHALL send only the `## README` section of the assembled markdown to a dedicated `knowledge_github_cleaner` agent and keep the structured signal sections (`## Repo Signals`, `## Project Layout`, `## Recent Releases`, `## Manifest`, `## Recent Commits`, `## Activity`) verbatim. The retention floor for the cleaned README SHALL be lower than the generic article floor so aggressive condensation is permitted; below the floor the workflow SHALL fail loud.

#### Scenario: README section is the only part cleaned

- **WHEN** a github artifact body is processed by `clean_body`
- **THEN** the structured signal sections above `## README` are preserved byte-for-byte in the output and only the README prose is replaced with the cleaner's output

#### Scenario: non-github source uses default cleaner

- **WHEN** the artifact's `source_type` is anything other than `"github"`
- **THEN** `clean_body` invokes the existing `knowledge_artifact_editor` agent under its existing rules and retention floor

#### Scenario: cleaner over-condensation fails loud

- **WHEN** `knowledge_github_cleaner` returns README markdown shorter than the github retention floor
- **THEN** the workflow raises a loud failure and no artifact is written

### Requirement: GitHub artifacts use a source-specific frontmatter agent

For `source_type == "github"` the artifact edit phase SHALL produce frontmatter via the `knowledge_github_summary` agent under the existing `FrontmatterDraft` schema. The github agent's prompt SHALL instruct the model to organize the single `summary` text around four perspectives: what the repo *does*, its *value* / why bookmark it, *maturity*, and *ecosystem*. The schema, the `to_artifact_edit()` contract, and the downstream `persist` / GBrain ingest path SHALL remain identical to other source types — only the agent identity and its prompt differ.

#### Scenario: github source routes to github summary agent

- **WHEN** the artifact's `source_type` is `"github"` and the artifact body is ready for frontmatter
- **THEN** `write_frontmatter` invokes the `knowledge_github_summary` agent under the `FrontmatterDraft` schema

#### Scenario: non-github source uses default frontmatter agent

- **WHEN** the artifact's `source_type` is anything other than `"github"`
- **THEN** `write_frontmatter` invokes the existing `knowledge_frontmatter` agent under the `FrontmatterDraft` schema

#### Scenario: github frontmatter validation failure is loud

- **WHEN** the `knowledge_github_summary` agent fails to produce a valid `FrontmatterDraft` (empty summary, no valid English tags, malformed freshness)
- **THEN** the workflow raises a loud failure and no artifact is written

### Requirement: GitHub raw store keeps metadata JSON and README original

The github fetcher SHALL write the raw `/repos/{owner}/{repo}` JSON response and the decoded README pre-truncation into the raw store, and SHALL set the artifact's `raw_path` to the README file.

#### Scenario: raw artifacts persist

- **WHEN** a github URL is ingested successfully
- **THEN** the raw store directory for the artifact contains both `metadata.json` (the repo API response) and `readme.md` (the original decoded README)

### Requirement: Category override skips classification

`ingest_one` and the ingest workflow SHALL accept an optional category override. When a valid taxonomy category is supplied, the classify step SHALL use it and NOT invoke the classifier agent; when omitted, automatic classification runs as before. An override that is not a declared taxonomy category SHALL be rejected with a loud error before fetch work begins, with no silent fallback.

#### Scenario: valid override bypasses the classifier

- **WHEN** `ingest_one(value, category="investing/quant")` is called with a taxonomy-valid path
- **THEN** the resulting artifact's category is `investing/quant` and the `knowledge_classifier` agent is not invoked

#### Scenario: omitted override classifies automatically

- **WHEN** `ingest_one(value)` is called with no category
- **THEN** the classify step runs the classifier agent as in current behavior

#### Scenario: invalid override fails loud

- **WHEN** `ingest_one(value, category="bogus")` is called with a path absent from the taxonomy
- **THEN** a loud error is raised and no artifact is written

### Requirement: Per-step progress callback

`ingest_one` and the ingest workflow SHALL accept an optional progress callback invoked as each pipeline step starts and completes, receiving an event identifying the step name and its status (start, done, or error). The callback SHALL be optional; when absent, ingest behaves exactly as today. The final result JSON shape SHALL be unchanged regardless of whether a callback is supplied.

#### Scenario: callback receives one event per step transition

- **WHEN** `ingest_one(value, on_progress=cb)` runs to completion for a supported input
- **THEN** `cb` is called with a start and a done event for each of the fetch, clean, enrich, classify, and persist steps

#### Scenario: callback reports a failing step

- **WHEN** a pipeline step raises during `ingest_one(value, on_progress=cb)`
- **THEN** `cb` receives an error event naming the failing step before the error propagates

#### Scenario: result shape unchanged with a callback

- **WHEN** `ingest_one(value, on_progress=cb)` completes successfully
- **THEN** the returned result still includes `ok`, `source_type`, `category`, `markdown_path`, `raw_path`, `frontmatter`, and optional `ingest` with their existing meanings

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

### Requirement: Workflow topology is fetch clean enrich classify persist

The knowledge ingest `Workflow` SHALL declare these steps in order:

1. `fetch` (`max_retries=2`)
2. `clean` (`max_retries=1`, runs `clean_body`)
3. `enrich` (`max_retries=1`, runs `write_frontmatter`)
4. `classify` (`max_retries=0`)
5. `persist` (`max_retries=0`)

All steps use `on_error=OnError.fail`. Each step SHALL be a thin adapter that unwraps `StepInput`, calls the corresponding stage function, and returns `StepOutput(content=artifact)`.

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

#### Scenario: an agent lists the workflow tool

- **WHEN** an agent YAML declares `tools: [knowledge_ingest_workflow]`
- **THEN** the registry resolves it to the workflow's `WorkflowTools` toolkit and no separate `knowledge_pipeline_workflow` wrapper exists

Note: no agent in this repo currently ships with `knowledge_ingest_workflow` in its `tools:` list (there is no `knowledge_manager` agent) — the mechanism above is exercised by `paca run-workflow knowledge_ingest` and the dashboard's re-index action, not by an agent-initiated tool call, as of this repo.

### Requirement: Manual run uses configured run function

The `paca run-workflow` CLI command SHALL use `WorkflowConfig.extra.run_now` for manual workflow execution.

#### Scenario: knowledge ingest runs manually

- **WHEN** `uv run paca run-workflow knowledge_ingest` is invoked
- **THEN** the CLI resolves `knowledge_ingest` to `paca.workflows.knowledge_ingest:run` and calls it

