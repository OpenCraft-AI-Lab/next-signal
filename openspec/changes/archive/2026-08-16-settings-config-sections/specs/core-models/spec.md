## MODIFIED Requirements

### Requirement: Production API stages apply live engine settings

For production stages routed to `omlx` or `deepseek`, the model factory SHALL construct the stage model from the appropriate static structured/plain profile while overriding the operator-controlled fields from the job's validated `engine.json`: OMLX base URL, model ID, and parallelism; DeepSeek model ID and reasoning mode. Embedders are outside this requirement's scope: `engine.json` SHALL NOT change which embedder runs or what it emits.

A production job SHALL NOT start when no engine has been selected — see "No engine is selected until an operator selects one" below, which this requirement depends on.

#### Scenario: OMLX selection uses live model and endpoint

- **WHEN** a job starts with `engine.json` selecting OMLX model `M`, endpoint `U`, and parallelism `P`
- **THEN** every LLM stage in that job uses model `M` at `U` under the `P`-slot provider limit while embeddings resolve independently of the LLM engine selection

#### Scenario: DeepSeek reasoning setting is applied

- **WHEN** a job starts with DeepSeek reasoning set to `off`, `low`, or `high`
- **THEN** its stage client disables thinking or supplies the corresponding reasoning effort without changing the Pydantic output contract

## ADDED Requirements

### Requirement: No engine is selected until an operator selects one

`next_signal.core.engine_preferences.EnginePreferences.primary` SHALL be optional. An absent `engine.json`, or a present one that records no primary, SHALL resolve to an **unselected** state rather than to any engine. `configs/models.yaml`'s `local` / `deepseek_smart` profiles SHALL supply suggested values for the OMLX and DeepSeek panes' own fields only — they SHALL NOT cause any engine to be treated as chosen.

`next_signal.agents.stage.stage_job()` SHALL raise a distinct `EngineNotSelected` error immediately, before constructing any job state or making any provider call, when the resolved engine preferences record no primary. This mirrors `core.embedding_preferences.EmbedderNotSelected`: a caller can tell "nobody has chosen one yet" from "the chosen one is broken." Unlike an unselected embedder, which the dedup gate catches and treats as a conservative degraded mode, an unselected engine SHALL NOT be caught and degraded by any production-stage caller — a stage job's entire purpose is an LLM call, so there is no reduced-but-still-useful mode to fall back to, and the error propagates to block the job.

This requirement governs production stage jobs only (`stage_job()` / `run_stage()`, used by info-radar analysis, info-radar recap, and knowledge ingest's LLM steps). AgentOS's statically-configured interactive agents SHALL be unaffected: they resolve their model directly from their own `configs/agents/*.yaml` profile and SHALL NOT consult `engine.json`'s primary selection.

#### Scenario: fresh install selects no engine

- **WHEN** no `engine.json` exists and a production stage job starts
- **THEN** `stage_job()` raises `EngineNotSelected` before any provider call, and no job state is constructed

#### Scenario: unselected is distinguishable from broken

- **WHEN** a caller catches an engine resolution failure
- **THEN** it can distinguish "no engine has been selected" (`EngineNotSelected`) from a configured engine that failed to respond (`StageInvocationError`)

#### Scenario: suggested values do not select an engine

- **WHEN** `configs/models.yaml`'s `local` profile names a provider and model
- **THEN** that value is available to prefill the OMLX pane's own fields and nothing about it causes any engine to be selected

#### Scenario: interactive AgentOS agents are unaffected

- **WHEN** no engine has been selected in `engine.json`
- **THEN** AgentOS's statically-configured interactive agents continue to resolve their model from their own YAML profile, unaffected by the unselected state

#### Scenario: an explicit null selection is equivalent to absence

- **WHEN** `engine.json` exists and explicitly records no primary
- **THEN** the resolved state is unselected, identically to a missing file
