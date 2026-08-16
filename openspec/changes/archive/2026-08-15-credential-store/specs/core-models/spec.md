## MODIFIED Requirements

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

## ADDED Requirements

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
