## Why

The current knowledge ingest path implements the right behavior, but the Agno workflow mostly wraps Python stages and router branches, which makes the code heavier than the agentic workflow model this project wants to exercise. Reworking the pipeline around an orchestrator agent plus a dedicated artifact editor agent should keep the same durable artifact guarantees while making the flow easier to build, inspect, and evolve.

## What Changes

- Replace the stage-heavy knowledge pipeline workflow with a single `knowledge_ingest` flow that fetches input, writes the wiki artifact, and optionally indexes it in GBrain.
- Add a `knowledge_orchestrator` agent that coordinates fetch, edit, validation, write, and optional GBrain ingest.
- Add a `knowledge_artifact_editor` agent that receives the fetched markdown packet and returns cleaned markdown plus frontmatter fields in one bounded context.
- Keep safety-critical and side-effecting operations in deterministic tools: source fetch, local file staging checks, SSRF-safe web fetch, validation, wiki writes, related search, and GBrain ingest.
- Fail loud when required LLM editing fails or returns invalid output; do not use deterministic fallback content to create a simplified artifact.
- Preserve the external `knowledge_ingest` / `paca knowledge ingest` result shape as a compatibility wrapper over the ingest workflow.
- Expose `knowledge_ingest_workflow` to `knowledge_manager` as the normal ingestion tool instead of exposing low-level `gbrain_ingest`.
- Preserve the rule that GBrain ingest failure must not lose the written wiki artifact.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `knowledge-pipeline`: Change the save pipeline contract to require agent-led ingestion with a dedicated artifact editor agent while preserving current artifact, validation, and ingest semantics.

## Impact

- Affected code: `configs/agents/`, `prompts/`, `src/paca/tools/knowledge/`, `src/paca/workflows/knowledge_ingest.py`, and knowledge pipeline tests.
- Affected behavior: workflow traces should expose the orchestrator/editor agent boundary more clearly, while CLI/tool output stays compatible.
- Affected systems: local wiki artifact writes, raw artifact storage, GBrain ingest/search integration, and source adapters for WeChat, Bilibili, YouTube, web, markdown, and MarkItDown-supported files.
