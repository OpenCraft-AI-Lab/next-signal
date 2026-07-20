# core-models

Multi-provider model factory. Profiles live in `configs/models.yaml`; agents reference profiles by name.

## Purpose

Switching models, tuning sampling, or swapping a provider must not require code changes — only edits to `configs/models.yaml`. Local OMLX (Qwen3) is the default; DeepSeek is the currently configured cloud fallback (Claude, OpenAI, and Gemini providers are also implemented and usable, but no shipped profile currently falls back to them).

## Requirements

### Requirement: Provider abstraction by profile

`paca.core.models.get_model(profile_name)` SHALL return an agno-compatible model instance based on the YAML profile's `provider` field (`omlx` / `claude` / `openai` / `gemini` / `deepseek`).

#### Scenario: profile resolves to provider

- **WHEN** an agent YAML declares `model_profile: local`
- **THEN** the factory reads the `local` entry in `configs/models.yaml` and instantiates the matching provider class (`omlx`) with the profile's parameters

### Requirement: OMLX endpoint sourced from environment

OMLX `base_url` and `api_key` SHALL be read only from `.env` via `paca.core.models.omlx_endpoint()`; no other module is allowed to read these env vars directly.

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
- **THEN** subsequent calls keep returning the fallback until `paca.core.models.reset_cache()` is invoked

### Requirement: Qwen3 sampling defaults are fixed

The OMLX builder (`_build_omlx`) SHALL apply fixed Qwen3-specific `extra_body` knobs (`top_k: 20`, `min_p: 0.05`, `chat_template_kwargs: {enable_thinking: false}`) regardless of profile, and SHALL disable mlx-lm's unstable native structured-output path (`supports_native_structured_outputs=False`) while keeping the OpenAI-standard `response_format` json_schema / xgrammar-constrained-decoding path enabled (`supports_json_schema_outputs=True`) — do not flip this pair; agno only emits `response_format` for agents that pass an `output_schema`. Temperature, `top_p`, and `max_tokens` are NOT hardcoded in the builder — they come from the profile (`configs/models.yaml`'s `local`/`local_structured` profiles currently set `temperature: 0.2`, `top_p: 0.85`).

#### Scenario: defaults survive YAML omission

- **WHEN** a profile does not specify `extra_body` overrides
- **THEN** the OMLX model is built with the documented fixed `top_k`/`min_p`/`enable_thinking` knobs, merged with any `extra.extra_body` overrides the profile does specify

#### Scenario: DeepSeek disables both structured-output flags

- **WHEN** the `deepseek` provider is built (`_build_deepseek`)
- **THEN** both `supports_native_structured_outputs` and `supports_json_schema_outputs` are `False`, since DeepSeek's API rejects `response_format` json_schema — the schema is instead conveyed via the prompt and enforced by `run_structured`'s parse/validate/repair pass

### Requirement: Embedder profiles are OMLX-only

`paca.core.models.get_embedder(profile_name)` SHALL resolve a named profile from `configs/models.yaml`'s `embedders:` section (default profile name `local`) and return an `embed(text: str) -> list[float]` callable that POSTs to the OMLX endpoint's OpenAI-compatible `/v1/embeddings` route via `omlx_endpoint()`. Connection failures, non-2xx responses, or malformed response bodies SHALL raise `RuntimeError` rather than returning a degraded result. Each `embed` call SHALL acquire the embedder provider's concurrency slot via `ProviderConcurrency`, same as LLM calls, so embedding and LLM inference don't oversubscribe the same local GPU.

#### Scenario: unknown embedder profile fails loud

- **WHEN** `get_embedder("nonexistent")` is called
- **THEN** a `KeyError` is raised listing the known embedder profiles

#### Scenario: embedder request failure is loud

- **WHEN** the OMLX `/v1/embeddings` endpoint is unreachable or returns a non-2xx status
- **THEN** `embed()` raises `RuntimeError`; callers (e.g. the info-radar-analysis dedup gate) decide their own fallback policy

### Requirement: Per-provider concurrency limits gate every model call

`paca.core.models.get_model` SHALL wrap every built model's `response`/`aresponse`/`response_stream`/`aresponse_stream` entry points so calls acquire a per-provider semaphore (`ProviderConcurrency`, configured from `configs/models.yaml`'s `concurrency:` section) before running, holding it for the full duration of a streamed response. This applies transparently to every agent, Team, Workflow, and `@tool` call that goes through the model factory.

#### Scenario: local OMLX calls are capped tightly

- **WHEN** more concurrent requests are made against an `omlx`-provider profile than `concurrency.omlx` allows
- **THEN** excess calls block on the semaphore rather than oversubscribing the single local GPU/MLX process
