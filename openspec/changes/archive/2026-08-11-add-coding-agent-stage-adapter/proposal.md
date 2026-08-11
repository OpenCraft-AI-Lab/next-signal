## Why

The Dashboard can select and configure Codex CLI or Claude Code CLI, and the bounded bridge can invoke both, but production workflows still construct agno agents from their YAML `model_profile` and therefore continue to use OMLX. A provider-neutral stage adapter is needed so one live engine selection consistently governs every LLM stage without pretending an agent CLI is an agno `Model`.

## What Changes

- Add a synchronous production-stage execution API that loads the existing agent YAML/prompt/language policy and routes the call to OMLX, DeepSeek, Codex CLI, or Claude Code CLI.
- Read `engine.json` in Python at job start, validate it strictly, and pin one selected engine for the whole job. A configured fallback may replace an unreachable primary only before the first successful LLM response; a job never mixes engines after that point.
- Reuse the existing Pydantic schemas for every structured stage. OMLX continues to use json-schema constrained decoding, DeepSeek continues to use prompt JSON plus validation, Claude Code receives its supported JSON-schema flag, and Codex receives the schema in its prompt. All routes share strict/JSON5 parsing and one schema-repair attempt.
- Route all current production LLM stages in info-radar analysis, radar recap, and knowledge ingest through the adapter. Deterministic stages, fetchers, embeddings, ANN search, persistence, and AgentOS registration remain unchanged.
- Apply the Dashboard's OMLX endpoint/model/parallelism and DeepSeek model/reasoning settings at call time as well as the existing explicit Codex/Claude settings.
- Keep direct interactive agents and AgentOS as agno agents; the CLI providers remain external one-shot stage workers and are not registered as agno models or agent tools.
- Isolate production CLI stages from untrusted article prompt injection with a
  dedicated no-tools provider profile and an empty per-invocation workspace;
  direct operator review/edit profiles remain unchanged.
- Make the AgentOS-exposed knowledge workflow and evaluation harnesses own a
  full-job affinity boundary, and record the actual evaluation engine/model.
- Centralize every OMLX endpoint/API-key lookup behind one resolver while
  preserving `models.omlx_endpoint()` as the public strict API.

## Capabilities

### New Capabilities

- `core-stage-execution`: Live engine selection, per-job engine affinity/fallback, provider-neutral plain/structured stage execution, and CLI schema delivery.

### Modified Capabilities

- `core-models`: Production model-backed stages use live OMLX/DeepSeek settings rather than only static profile values, while embedders remain independently configured.
- `info-radar-analysis`: Tier 1, Tier 2, and the dedup judge use the production stage adapter instead of requiring OMLX constrained decoding.
- `info-radar-recap`: Recap generation uses the selected production engine with the same `RecapOutput` validation contract.
- `knowledge-pipeline`: Cleaner, frontmatter, GitHub enrichment, and classification LLM passes use the selected production engine without changing artifact contracts.

## Impact

- Python: new live engine-preference and stage-execution modules; small model-factory extension; coding-agent request/Claude argv schema support; production workflow call sites.
- Configuration: CLI concurrency entries in `configs/models.yaml`, a no-tools
  `stage` profile in `configs/coding_agents.yaml`; existing `engine.json` and
  `coding-agents.json` become active runtime inputs.
- Dashboard/docs: remove the “selection is not yet read” caveat and document job-scoped selection/fallback.
- No production database migration, new dependency, arbitrary command surface,
  or provider credential handling is introduced. Evaluation metadata reuses its
  existing digest/notes columns.
