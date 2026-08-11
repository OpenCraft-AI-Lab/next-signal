## ADDED Requirements

### Requirement: One resolved embedder snapshot owns one item's vector and identity

`next_signal.core.models.get_embedder()` SHALL take no arguments and SHALL read
the live embedding preferences and current process environment once, returning an
immutable `ResolvedEmbedder` containing the resolved provider, model, stable
vector-space identity, and an `embed(text: str) -> list[float]` callable. The
callable SHALL use the endpoint and credential captured by that same snapshot.

The consumer SHALL carry the snapshot's identity beside the returned vector
through search and persistence. It SHALL NOT re-read live state to determine
which identity to store after the embedding request has started.

State is resolved per item rather than cached for the process lifetime. A
settings change while one item is in flight SHALL affect the next item, not the
identity or endpoint of the current item.

#### Scenario: settings change during one embedding

- **WHEN** item A resolves provider A and `embedding.json` changes to provider B
  before item A is persisted
- **THEN** item A is searched and stored with provider A's captured identity,
  and the next item resolves provider B

#### Scenario: the resolved object is provider-neutral

- **WHEN** the dedup gate calls `get_embedder()` under any supported provider
- **THEN** it receives the same `ResolvedEmbedder` contract and contains no
  provider-specific branch

### Requirement: Real profiles supply baselines and generic configuration is explicit

`configs/models.yaml::embedders` SHALL remain the baseline for providers with
real shipped defaults. `embedders.local` supplies the fresh-install OMLX
selection/model and `embedders.openai` supplies the OpenAI model. An absent
`embedding.json` SHALL select the local baseline and SHALL NOT be an error.

For OMLX and OpenAI sections, fields absent from a partial state file SHALL
inherit from the matching `models.yaml` baseline. OpenAI-compatible configuration
SHALL be optional but all-or-nothing: no universal endpoint, model, key-variable
name, or vector-space id SHALL be invented. Selecting `openai_compatible` without
a complete saved section SHALL raise `RuntimeError` before any HTTP request.

The backend and Dashboard SHALL derive the two real baselines from the same YAML
profiles. `EmbedderProfile.provider` SHALL accept all supported providers.

#### Scenario: fresh install selects local embedding

- **WHEN** `embedding.json` does not exist
- **THEN** `get_embedder()` resolves `embedders.local` from `models.yaml`

#### Scenario: OpenAI partial state inherits its model

- **WHEN** state selects `openai` without overriding its model
- **THEN** the model resolves from `embedders.openai`

#### Scenario: generic provider has no fabricated default

- **WHEN** state selects `openai_compatible` but has no complete compatible section
- **THEN** resolution raises an actionable `RuntimeError` before any request

### Requirement: Three embedding providers are supported

`ResolvedEmbedder.embed()` SHALL dispatch using the provider captured in its
snapshot:

- `omlx` — POST to the centralized OMLX API root's `/embeddings` route, with
  endpoint and optional key resolved through the centralized OMLX resolver; do
  not send `dimensions`.
- `openai` — POST to `https://api.openai.com/v1/embeddings` with
  `OPENAI_API_KEY`, sending `dimensions: 1024`.
- `openai_compatible` — append `/embeddings` to the configured API root, use the
  credential from the configured environment-variable name, and send
  `dimensions: 1024`.

Unknown providers, missing required credentials, connection failures, non-2xx
responses, and malformed bodies SHALL raise `RuntimeError` rather than returning
a degraded value.

#### Scenario: hosted provider requests fixed width

- **WHEN** OpenAI model `text-embedding-3-small` embeds text
- **THEN** the request carries `dimensions: 1024`

#### Scenario: compatible API root receives the embeddings route

- **WHEN** compatible state saves `base_url=https://host.example/v1`
- **THEN** the request target is `https://host.example/v1/embeddings`

#### Scenario: unreachable endpoint fails loud

- **WHEN** the captured endpoint refuses the connection or returns non-2xx
- **THEN** `embed()` raises `RuntimeError` and returns no vector

### Requirement: Embedding state is strict and cannot carry a secret value

`~/.next-signal/embedding.json` SHALL reject unknown top-level or section keys,
invalid model identifiers, malformed key-variable names, malformed vector-space
ids, and invalid compatible API roots.

The compatible section SHALL contain `base_url`, `model`, `api_key_env`, and
`space_id`. `api_key_env` stores only an environment-variable name validated
against `^[A-Z][A-Z0-9_]{0,63}$`; `space_id` SHALL match
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`.

`base_url` SHALL be an `http` or `https` API root with a host. URL username,
password, query, and fragment components SHALL be rejected so a credential
cannot be persisted through the URL. A path already ending in `/embeddings`
SHALL be rejected; the client normalizes a trailing slash and appends that route
itself.

Credentials SHALL be resolved from the current process environment only when
`get_embedder()` constructs a snapshot. A missing credential SHALL NOT prevent
process startup. Editing `.env` SHALL NOT be described as hot-reload: a host
process must restart, and a Compose service must be recreated, before an updated
file value exists in that process environment.

#### Scenario: secret-bearing URL is rejected

- **WHEN** a compatible base URL contains userinfo or an API key in its query
- **THEN** validation rejects the state and no value is written

#### Scenario: environment variable name is stored, not its value

- **WHEN** compatible settings are saved
- **THEN** state contains `api_key_env` and no resolved credential value

#### Scenario: process environment is read for the next item

- **WHEN** the named variable is programmatically added to the running process
  before the next `get_embedder()` call
- **THEN** the next snapshot captures it without caching the prior absence

#### Scenario: editing dotenv requires lifecycle action

- **WHEN** an operator changes `.env` for a running scheduler or Compose service
- **THEN** documentation and diagnostics instruct them to restart the host
  process or recreate the service before expecting the value to change

### Requirement: Every returned embedding is exactly 1024 finite numbers

`embed()` SHALL validate that the provider response contains a JSON array of
exactly 1024 finite numeric elements. It SHALL raise `RuntimeError` naming the
failure for a wrong length, non-numeric value, `NaN`, or infinity. It SHALL NOT
truncate, pad, normalize, or return a partially valid vector.

This keeps `radar_pushed_topics.embedding` at `vector(1024)` across provider
switches and excludes models that cannot produce the fixed width.

#### Scenario: wrong-width model is rejected

- **WHEN** a provider returns 1536 elements
- **THEN** `embed()` reports 1024 expected and 1536 received, and nothing is stored

#### Scenario: non-finite vector is rejected

- **WHEN** one of 1024 elements is `NaN` or infinity
- **THEN** `embed()` raises before the vector reaches pgvector

#### Scenario: correct vector passes unchanged

- **WHEN** a provider returns exactly 1024 finite numbers
- **THEN** the vector is returned without normalization or resizing

### Requirement: Every new vector carries a stable vector-space identity

The capability SHALL expose the identity captured in `ResolvedEmbedder`:

- OMLX: `omlx:<model_id>`
- OpenAI: `openai:<model_id>`
- OpenAI-compatible: `openai_compatible:<space_id>`

The compatible `space_id` is operator-managed and SHALL change whenever weights,
tokenizer, pooling, quantization, dimension behavior, or any other
vector-producing behavior changes. A transport-only base URL change SHALL NOT
force an identity change.

The provider's advertised model name SHALL NOT replace `space_id` for generic
endpoints, because different endpoints may use the same name for incompatible
vector spaces.

#### Scenario: compatible endpoint moves without changing vectors

- **WHEN** a compatible service moves to a new base URL while retaining the same
  vector-producing implementation and `space_id`
- **THEN** its identity remains stable and its existing rows remain searchable

#### Scenario: compatible implementation changes

- **WHEN** the endpoint's weights, tokenizer, pooling, or quantization changes
- **THEN** the operator saves a new `space_id`, producing a new identity that
  cannot compare against the earlier rows

### Requirement: Embedding has no provider fallback

No embedding provider SHALL automatically fall back to another. A failed
embedding SHALL raise `RuntimeError` to the consumer, which owns the conservative
`novel` policy.

#### Scenario: down provider does not switch vector space

- **WHEN** the selected provider is unreachable and another is configured
- **THEN** the call raises and no other provider is attempted

### Requirement: Embedding uses the resolved provider's concurrency slot

Each `embed()` call SHALL acquire `ProviderConcurrency` using the provider
captured by its `ResolvedEmbedder`. OMLX embedding therefore contends with OMLX
LLM inference for the local GPU; hosted embedding does not consume that slot.

#### Scenario: local embedding shares the local cap

- **WHEN** OMLX LLM stages saturate the OMLX cap
- **THEN** an OMLX embedding waits for a slot

#### Scenario: hosted embedding does not block on OMLX

- **WHEN** OpenAI is selected while the OMLX cap is saturated
- **THEN** embedding proceeds under OpenAI's provider slot

### Requirement: Doctor reports the active snapshot configuration

`next-signal doctor` SHALL report the resolved identity and whether its required
credential exists in the current process environment. Invalid embedding state or
a missing credential SHALL produce a failed check and a non-zero exit. Doctor
SHALL NOT issue an embedding request.

For OMLX, the configured base URL is required and `OMLX_API_KEY` remains optional;
an absent optional key SHALL NOT fail the embedder check. OpenAI and
OpenAI-compatible credentials are required.

When a variable is absent, the message SHALL use accurate lifecycle guidance:
restart a host process or recreate a Compose service after changing `.env`.

#### Scenario: hosted selection has no key

- **WHEN** OpenAI is selected and `OPENAI_API_KEY` is absent
- **THEN** doctor reports a failed embedder check naming the variable and exits non-zero

#### Scenario: valid selection is reported without a request

- **WHEN** state and credential are valid
- **THEN** doctor reports the identity successfully and performs no HTTP call
