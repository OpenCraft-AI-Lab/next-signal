# core-models

Multi-provider model factory. Profiles live in `configs/models.yaml`; agents reference profiles by name.

## Purpose

Switching models, tuning sampling, or swapping a provider must not require code changes — only edits to `configs/models.yaml`. Local OMLX (Qwen3) is the default; cloud models (Claude, OpenAI, Gemini) are fallbacks.

## Requirements

### Requirement: Provider abstraction by profile

`paca.core.models.get_model(profile_name)` SHALL return an agno-compatible model instance based on the YAML profile's `provider` field (`omlx` / `claude` / `openai` / `gemini`).

#### Scenario: profile resolves to provider

- **WHEN** an agent declares `model: large_local`
- **THEN** the factory reads the `large_local` entry in `configs/models.yaml` and instantiates the matching provider class with the profile's parameters

### Requirement: OMLX endpoint sourced from environment

OMLX `base_url` and `api_key` SHALL be read only from `.env` via `paca.core.models.omlx_endpoint()`; no other module is allowed to read these env vars directly.

#### Scenario: missing endpoint configuration fails loud

- **WHEN** `OMLX_BASE_URL` is unset or invalid
- **THEN** `omlx_endpoint()` raises `RuntimeError`

### Requirement: Automatic fallback when OMLX unreachable

When an OMLX-backed profile fails to construct (`RuntimeError`) and the profile declares a `fallback_profile`, `get_model` SHALL transparently return the fallback profile's model.

#### Scenario: fallback to Claude when OMLX is down

- **WHEN** OMLX is unreachable and the profile lists `fallback_profile: medium_cloud`
- **THEN** `get_model` returns the `medium_cloud` model and logs the substitution

#### Scenario: cache must be reset to retry OMLX

- **WHEN** OMLX recovers after a fallback occurred
- **THEN** subsequent calls keep returning the fallback until `paca.core.models.reset_cache()` is invoked

### Requirement: Qwen3 sampling defaults are fixed

The OMLX builder SHALL apply the tuned Qwen3 sampling defaults (temperature 0.4, top_p 0.85, min_p 0.05, thinking disabled) and disable mlx-lm's unstable `json_schema` paths via `supports_native_structured_outputs=False` and `supports_json_schema_outputs=False`.

#### Scenario: defaults survive YAML omission

- **WHEN** a profile does not specify sampling parameters
- **THEN** the OMLX model is built with the documented Qwen3 defaults
