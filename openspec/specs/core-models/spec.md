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

### Requirement: OMLX endpoint sourced from environment

OMLX `base_url` SHALL be read only from `.env` via
`next_signal.core.models.omlx_endpoint()`; no other module is allowed to read
that env var directly. The OMLX `api_key` SHALL be resolved from the credential
store at call time by the same resolver, so the endpoint is assembled from one
place even though its two halves have different sources. `OMLX_API_KEY` remains
optional — a local OMLX server usually has none.

#### Scenario: missing endpoint configuration fails loud

- **WHEN** `OMLX_BASE_URL` is unset or invalid
- **THEN** `omlx_endpoint()` raises `RuntimeError`

#### Scenario: OMLX key comes from the store

- **WHEN** `OMLX_API_KEY` is present in the credential store
- **THEN** `omlx_endpoint()` returns it, and it is not read from the process
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

### Requirement: Saving a credential invalidates cached models

Cached model instances hold the credential captured when they were built.
Writing the credential store SHALL invalidate that cache, so a credential
corrected in the dashboard takes effect on the next model use rather than
persisting until the process restarts.

#### Scenario: corrected credential takes effect without restart

- **WHEN** a model has been built with a credential that is then replaced in the
  store
- **THEN** the next `get_model` call builds against the new credential

### Requirement: Automatic fallback when OMLX unreachable

When an OMLX-backed profile fails to construct (`RuntimeError`) and the profile declares a `fallback_profile`, `get_model` SHALL transparently return the fallback profile's model.

#### Scenario: fallback to DeepSeek when OMLX is down

- **WHEN** OMLX is unreachable and the profile lists `fallback_profile: deepseek_smart` (as `local` does in `configs/models.yaml`)
- **THEN** `get_model` returns the `deepseek_smart` model and logs the substitution

#### Scenario: cache must be reset to retry OMLX

- **WHEN** OMLX recovers after a fallback occurred
- **THEN** subsequent calls keep returning the fallback until `next_signal.core.models.reset_cache()` is invoked

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

For production stages routed to `omlx` or `deepseek`, the model factory SHALL construct the stage model from the appropriate static structured/plain profile while overriding the operator-controlled fields from the job's validated `engine.json`: OMLX base URL, model ID, and parallelism; DeepSeek model ID and reasoning mode. These runtime stage clients SHALL not alter the cached YAML-profile models used by AgentOS. Embedders are outside this requirement's scope: `engine.json` SHALL NOT change which embedder runs or what it emits.

#### Scenario: OMLX selection uses live model and endpoint

- **WHEN** a job starts with `engine.json` selecting OMLX model `M`, endpoint `U`, and parallelism `P`
- **THEN** every LLM stage in that job uses model `M` at `U` under the `P`-slot provider limit while embeddings resolve independently of the LLM engine selection

#### Scenario: DeepSeek reasoning setting is applied

- **WHEN** a job starts with DeepSeek reasoning set to `off`, `low`, or `high`
- **THEN** its stage client disables thinking or supplies the corresponding reasoning effort without changing the Pydantic output contract

### Requirement: OMLX endpoint resolution has one environment reader

Every OMLX model, embedder, live-engine default, and diagnostic SHALL resolve
`OMLX_BASE_URL` / `OMLX_API_KEY` through the centralized core resolver. The
public `next_signal.core.models.omlx_endpoint()` SHALL remain the strict API for
callers that require a configured environment and SHALL delegate to that resolver.

#### Scenario: Live engine default resolves OMLX consistently

- **WHEN** `OMLX_BASE_URL` is set before engine defaults are constructed
- **THEN** engine preferences and the public model endpoint return the same normalized base URL without either duplicating environment access

