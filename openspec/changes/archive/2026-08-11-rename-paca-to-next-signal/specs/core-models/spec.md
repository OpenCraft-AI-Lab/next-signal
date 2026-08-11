## MODIFIED Requirements

### Requirement: Provider abstraction by profile

`next_signal.core.models.get_model(profile_name)` SHALL return an agno-compatible model instance based on the YAML profile's `provider` field (`omlx` / `claude` / `openai` / `gemini` / `deepseek`).

#### Scenario: profile resolves to provider

- **WHEN** an agent YAML declares `model_profile: local`
- **THEN** the factory reads the `local` entry in `configs/models.yaml` and instantiates the matching provider class (`omlx`) with the profile's parameters

### Requirement: OMLX endpoint sourced from environment

OMLX `base_url` and `api_key` SHALL be read only from `.env` via `next_signal.core.models.omlx_endpoint()`; no other module is allowed to read these env vars directly.

#### Scenario: missing endpoint configuration fails loud

- **WHEN** `OMLX_BASE_URL` is unset or invalid
- **THEN** `omlx_endpoint()` raises `RuntimeError`

### Requirement: Automatic fallback when OMLX unreachable

When an OMLX-backed profile fails to construct (`RuntimeError`) and the profile declares a `fallback_profile`, `get_model` SHALL transparently return the fallback profile's model.

#### Scenario: fallback to DeepSeek when OMLX is down

- **WHEN** OMLX is unreachable and the profile lists `fallback_profile: deepseek_smart` (as `local` does in `configs/models.yaml`)
- **THEN** `get_model` returns the `deepseek_smart` model and logs the substitution

#### Scenario: cache must be reset to retry OMLX

- **WHEN** OMLX recovers after a fallback occurred
- **THEN** subsequent calls keep returning the fallback until `next_signal.core.models.reset_cache()` is invoked

### Requirement: Embedder profiles are OMLX-only

`next_signal.core.models.get_embedder(profile_name)` SHALL resolve a named profile from `configs/models.yaml`'s `embedders:` section (default profile name `local`) and return an `embed(text: str) -> list[float]` callable that POSTs to the OMLX endpoint's OpenAI-compatible `/v1/embeddings` route via `omlx_endpoint()`. Connection failures, non-2xx responses, or malformed response bodies SHALL raise `RuntimeError` rather than returning a degraded result. Each `embed` call SHALL acquire the embedder provider's concurrency slot via `ProviderConcurrency`, same as LLM calls, so embedding and LLM inference don't oversubscribe the same local GPU.

#### Scenario: unknown embedder profile fails loud

- **WHEN** `get_embedder("nonexistent")` is called
- **THEN** a `KeyError` is raised listing the known embedder profiles

#### Scenario: embedder request failure is loud

- **WHEN** the OMLX `/v1/embeddings` endpoint is unreachable or returns a non-2xx status
- **THEN** `embed()` raises `RuntimeError`; callers (e.g. the info-radar-analysis dedup gate) decide their own fallback policy

### Requirement: Per-provider concurrency limits gate every model call

`next_signal.core.models.get_model` SHALL wrap every built model's `response`/`aresponse`/`response_stream`/`aresponse_stream` entry points so calls acquire a per-provider semaphore (`ProviderConcurrency`, configured from `configs/models.yaml`'s `concurrency:` section) before running, holding it for the full duration of a streamed response. This applies transparently to every agent, Team, Workflow, and `@tool` call that goes through the model factory.

#### Scenario: local OMLX calls are capped tightly

- **WHEN** more concurrent requests are made against an `omlx`-provider profile than `concurrency.omlx` allows
- **THEN** excess calls block on the semaphore rather than oversubscribing the single local GPU/MLX process
