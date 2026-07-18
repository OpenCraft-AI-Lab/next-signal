## 1. Agent Contracts

- [x] 1.1 Add `knowledge_artifact_editor` agent config and prompt with a fixed JSON output schema for cleaned markdown, title, summary, tags, freshness, and related queries
- [x] 1.2 Add `knowledge_orchestrator` agent config and prompt that calls tools for fetch, edit, validate, write, and optional ingest
- [x] 1.3 Add config/loader tests proving both new agents load with the expected model, tools, shared-context posture, and DB posture

## 2. Deterministic Tool Boundary

- [x] 2.1 Add a unified source fetch tool/helper that wraps current source detection and fetch adapters into a JSON-safe source packet
- [x] 2.2 Add an artifact edit validation helper that rejects empty markdown, transcript summarization, invented headings, invalid freshness, invalid tags, and empty summary
- [x] 2.3 Add or adapt related-search, artifact-write, and GBrain-ingest helpers so the orchestrator never writes files or invokes GBrain directly
- [x] 2.4 Add focused tests for fetch packet shape, validation failure cases, LLM/editor failure loud errors, artifact write output, and ingest failure preservation

## 3. Agent-Led Save Flow

- [x] 3.1 Route `paca knowledge ingest` through the `knowledge_ingest` workflow while preserving the public result shape
- [x] 3.2 Expose `knowledge_ingest_workflow` as the manager-facing workflow tool and keep `knowledge_pipeline_workflow` only as a compatibility alias
- [x] 3.3 Cap editor retry behavior after validation feedback and surface non-ingest failures as loud errors
- [x] 3.4 Update `knowledge_manager` prompt/tool references to use `knowledge_ingest_workflow` as the normal ingestion path

## 4. Legacy Cleanup

- [x] 4.1 Remove obsolete stage adapters only after replacement tests cover their behavior
- [x] 4.2 Remove fallback wiring from legacy cleaner/enricher prompts or keep them only as unused implementation reference during the migration
- [x] 4.3 Update progress/docs notes for the new agent-led architecture without changing unrelated wiki content

## 5. Verification

- [x] 5.1 Run focused knowledge pipeline tests for fetch, validation, write, workflow, and save compatibility
- [x] 5.2 Run `uv run pytest -q`
- [x] 5.3 Run `openspec validate --all`
- [x] 5.4 If local GBrain is available, run an isolated test-brain smoke for one supported source through save, artifact write, ingest, and search
