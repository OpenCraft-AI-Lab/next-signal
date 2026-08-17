# core-models

Multi-provider model factory. Profiles live in `configs/models.yaml`; agents reference profiles by name.

## Purpose

Switching models, tuning sampling, or swapping a provider must not require code changes — only edits to `configs/models.yaml`. Local OMLX (Qwen3) is the default; DeepSeek is the currently configured cloud fallback (Claude, OpenAI, and Gemini providers are also implemented and usable, but no shipped profile currently falls back to them).
## Requirements
### Requirement: Provider abstraction by profile

`next_signal.core.models.get_model(profile_name)` SHALL return an agno-compatible model instance based on the YAML profile's `provider` field (`omlx` / `claude` / `openai` / `gemini` / `deepseek`).

#### Scenario: profile resolves to provider

- **WHEN** an agent YAML declares `model_profile: local`
- **THEN** the factory reads the `local` entry in `configs/models.yaml` and instantiates the matching provider class (`omlx`) with the profile's parameters

### Requirement: OMLX endpoint sourced from user state

The OMLX `base_url` for LLM profiles SHALL be read from the engine preferences
in user state (`engine.json`), not from the process environment. No module SHALL
read an `OMLX_BASE_URL` environment variable; that variable SHALL NOT be part of
the system's configuration surface.

The OMLX `api_key` SHALL be resolved from the credential store at call time by
the same resolver, so the endpoint is assembled from one place even though its
two halves have different sources. `OMLX_API_KEY` remains optional — a local
OMLX server usually has none.

Every consumer of a local LLM endpoint — static YAML profiles used by AgentOS,
live engine stages, and diagnostics — SHALL resolve it from engine preferences,
so the local chat endpoint has exactly one home. The embedding capability owns
its own OMLX API root separately, because one local model server hosts one
model.

#### Scenario: missing endpoint configuration fails loud

- **WHEN** engine preferences record no OMLX base URL
- **THEN** endpoint resolution raises `RuntimeError`, which an OMLX profile
  handles through its configured `fallback_profile`

#### Scenario: environment is not an endpoint source

- **WHEN** `OMLX_BASE_URL` is set in the process environment
- **THEN** it has no effect, because no module reads it

#### Scenario: OMLX key comes from the store

- **WHEN** `OMLX_API_KEY` is present in the credential store
- **THEN** endpoint resolution returns it, and it is not read from the process
  environment

### Requirement: Cloud model constructors receive credentials explicitly

The model factory SHALL pass the resolved credential to each cloud provider's
constructor explicitly, and SHALL raise `RuntimeError` naming the credential
*before* constructing the model when the store does not hold it.

This is required rather than stylistic: the underlying agno model classes fall
back to reading their own provider environment variable when constructed without
a key, which would resolve a credential from a source this system has declared
it does not read.

#### Scenario: missing credential raises before construction

- **WHEN** a `claude`, `openai`, `gemini`, or `deepseek` profile is built and the
  store holds no credential for it
- **THEN** the factory raises `RuntimeError` naming the credential, and no model
  instance is constructed

#### Scenario: provider SDK cannot reach the environment

- **WHEN** a provider's environment variable is set in the process but the store
  holds no credential for it
- **THEN** the model is not constructed and the environment value is not used

### Requirement: Built models are not cached across calls

`get_model(profile_name)` SHALL construct a model each time it is called. The
profile name SHALL NOT be treated as a cache key, because the endpoint and
credentials a model is built from now live in user state that can change while
a process runs, so the name no longer determines the result.

No cache-invalidation entry point SHALL exist for built models, and saving a
credential SHALL NOT need to clear one.

A caller that retains a constructed model — notably AgentOS, which builds its
agents once at startup — continues to use the endpoint and credential captured
at construction. Interfaces that let an operator change those values SHALL state
that already-running interactive agents pick up the change on restart. Paths
that resolve per job or per item — production stages and embedding — are
unaffected and observe changes immediately.

#### Scenario: a profile is rebuilt on each request

- **WHEN** `get_model` is called twice for the same profile with different
  endpoint settings saved in between
- **THEN** the second call returns a model built against the second endpoint

#### Scenario: recovery needs no manual reset

- **WHEN** an OMLX profile fell back to its cloud profile while the local server
  was unreachable, and the server later recovers
- **THEN** the next `get_model` call for that profile builds OMLX again without
  any cache-clearing call

#### Scenario: retained models keep their construction-time settings

- **WHEN** an operator changes the local endpoint while AgentOS is running
- **THEN** its already-constructed interactive agents continue against the
  previous endpoint until the process restarts, and the settings interface says so

### Requirement: Automatic fallback when OMLX unreachable

When an OMLX-backed profile fails to construct (`RuntimeError`) and the profile declares a `fallback_profile`, `get_model` SHALL transparently return the fallback profile's model.

#### Scenario: fallback to DeepSeek when OMLX is down

- **WHEN** OMLX is unreachable and the profile lists `fallback_profile: deepseek_smart` (as `local` does in `configs/models.yaml`)
- **THEN** `get_model` returns the `deepseek_smart` model and logs the substitution

#### Scenario: cache must be reset to retry OMLX

- **WHEN** OMLX recovers after a fallback occurred
- **THEN** the next `get_model` call returns the OMLX model again, because
  nothing is cached and no reset step exists

### Requirement: Qwen3 sampling defaults are fixed

The OMLX builder (`_build_omlx`) SHALL apply fixed Qwen3-specific `extra_body` knobs (`top_k: 20`, `min_p: 0.05`, `chat_template_kwargs: {enable_thinking: false}`) regardless of profile, and SHALL disable mlx-lm's unstable native structured-output path (`supports_native_structured_outputs=False`) while keeping the OpenAI-standard `response_format` json_schema / xgrammar-constrained-decoding path enabled (`supports_json_schema_outputs=True`) — do not flip this pair; agno only emits `response_format` for agents that pass an `output_schema`. Temperature, `top_p`, and `max_tokens` are NOT hardcoded in the builder — they come from the profile (`configs/models.yaml`'s `local`/`local_structured` profiles currently set `temperature: 0.2`, `top_p: 0.85`).

#### Scenario: defaults survive YAML omission

- **WHEN** a profile does not specify `extra_body` overrides
- **THEN** the OMLX model is built with the documented fixed `top_k`/`min_p`/`enable_thinking` knobs, merged with any `extra.extra_body` overrides the profile does specify

#### Scenario: DeepSeek disables both structured-output flags

- **WHEN** the `deepseek` provider is built (`_build_deepseek`)
- **THEN** both `supports_native_structured_outputs` and `supports_json_schema_outputs` are `False`, since DeepSeek's API rejects `response_format` json_schema — the schema is instead conveyed via the prompt and enforced by `run_structured`'s parse/validate/repair pass

### Requirement: Per-provider concurrency limits gate every model call

`next_signal.core.models.get_model` SHALL wrap every built model's `response`/`aresponse`/`response_stream`/`aresponse_stream` entry points so calls acquire a per-provider semaphore (`ProviderConcurrency`, configured from `configs/models.yaml`'s `concurrency:` section) before running, holding it for the full duration of a streamed response. This applies transparently to every agent, Team, Workflow, and `@tool` call that goes through the model factory.

#### Scenario: local OMLX calls are capped tightly

- **WHEN** more concurrent requests are made against an `omlx`-provider profile than `concurrency.omlx` allows
- **THEN** excess calls block on the semaphore rather than oversubscribing the single local GPU/MLX process

### Requirement: Production API stages apply live engine settings

For production stages routed to `omlx` or `deepseek`, the model factory SHALL construct the stage model from the appropriate static structured/plain profile while overriding the operator-controlled fields from the job's validated `engine.json`: OMLX base URL, model ID, and parallelism; DeepSeek model ID and reasoning mode. Embedders are outside this requirement's scope: `engine.json` SHALL NOT change which embedder runs or what it emits.

A production job SHALL NOT start when no engine has been selected — see "No engine is selected until an operator selects one" below, which this requirement depends on.

#### Scenario: OMLX selection uses live model and endpoint

- **WHEN** a job starts with `engine.json` selecting OMLX model `M`, endpoint `U`, and parallelism `P`
- **THEN** every LLM stage in that job uses model `M` at `U` under the `P`-slot provider limit while embeddings resolve independently of the LLM engine selection

#### Scenario: DeepSeek reasoning setting is applied

- **WHEN** a job starts with DeepSeek reasoning set to `off`, `low`, or `high`
- **THEN** its stage client disables thinking or supplies the corresponding reasoning effort without changing the Pydantic output contract

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

### Requirement: OMLX endpoint resolution has one state reader

Every OMLX model, live-engine default, and diagnostic that needs the local chat
endpoint SHALL resolve it through the centralized core resolver reading engine
preferences and the credential store. The public
`next_signal.core.models.omlx_endpoint()` SHALL remain the strict API for
callers that require a configured endpoint and SHALL delegate to that resolver.

#### Scenario: Live engine default resolves OMLX consistently

- **WHEN** engine preferences record an OMLX base URL
- **THEN** engine defaults and the public model endpoint return the same
  normalized base URL without either duplicating state access

