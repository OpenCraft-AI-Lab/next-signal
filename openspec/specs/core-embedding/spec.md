# core-embedding Specification

## Purpose
TBD - created by archiving change switchable-embedding-provider. Update Purpose after archive.
## Requirements

### Requirement: One resolved embedder snapshot owns one item's vector and identity

`next_signal.core.models.get_embedder()` SHALL take no arguments and SHALL read
the live embedding preferences and the credential store once, returning an
immutable `ResolvedEmbedder` containing the resolved provider, model, stable
vector-space identity, and an `embed(text: str) -> list[float]` callable. The
callable SHALL use the endpoint and credential captured by that same snapshot.

When no embedder is selected, no snapshot SHALL be produced; the caller learns
the selection is absent rather than receiving an embedder that cannot work.

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

#### Scenario: no snapshot exists while unselected

- **WHEN** `get_embedder()` is called and no provider is selected
- **THEN** it raises without producing a snapshot and without contacting any
  endpoint

### Requirement: Three embedding providers are supported

`ResolvedEmbedder.embed()` SHALL dispatch using the provider captured in its
snapshot:

- `omlx` — POST to the `/embeddings` route of the API root recorded in the
  embedding state's own OMLX section, with no credential; do not send
  `dimensions`.
- `openai` — POST to `https://api.openai.com/v1/embeddings` with the
  `RADAR_EMBEDDING_OPENAI_API_KEY` credential from the credential store,
  sending `dimensions: 1024`.
- `openai_compatible` — append `/embeddings` to the configured API root, use the
  `EMBEDDING_API_KEY` credential from the credential store, and send
  `dimensions: 1024`.

The OMLX embedding endpoint SHALL be the one recorded in embedding state, which
is independent of the LLM engine's OMLX endpoint: one local model server hosts
one model, so a chat model and an embedding model are separately addressed.

Unknown providers, missing required credentials, connection failures, non-2xx
responses, and malformed bodies SHALL raise `RuntimeError` rather than returning
a degraded value.

#### Scenario: hosted provider requests fixed width

- **WHEN** OpenAI model `text-embedding-3-small` embeds text
- **THEN** the request carries `dimensions: 1024`

#### Scenario: compatible API root receives the embeddings route

- **WHEN** compatible state saves `base_url=https://host.example/v1`
- **THEN** the request target is `https://host.example/v1/embeddings`

#### Scenario: embedding and chat endpoints are independent

- **WHEN** embedding state records one OMLX API root and engine state records a
  different one
- **THEN** embedding requests go to the embedding root and LLM requests go to
  the engine root, with neither overriding the other

#### Scenario: unreachable endpoint fails loud

- **WHEN** the captured endpoint refuses the connection or returns non-2xx
- **THEN** `embed()` raises `RuntimeError` and returns no vector

#### Scenario: the radar OpenAI credential is independent of GBrain's

- **WHEN** the `openai` provider embeds text
- **THEN** it resolves `RADAR_EMBEDDING_OPENAI_API_KEY`, never `OPENAI_API_KEY`
  — the name GBrain's own OpenAI embedding provider reads from its own
  environment

### Requirement: Embedding state is strict and cannot carry a secret value

`~/.next-signal/embedding.json` SHALL reject unknown top-level or section keys,
invalid model identifiers, malformed vector-space ids, and invalid API roots.

The OMLX section SHALL contain `base_url` and `model`. The OpenAI section SHALL
contain `model`. The compatible section SHALL contain `base_url`, `model`, and
`space_id`. `space_id` SHALL match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`.

No section SHALL name a credential. Credentials are resolved by fixed name —
`RADAR_EMBEDDING_OPENAI_API_KEY` and `EMBEDDING_API_KEY` respectively for the
`openai` and `openai_compatible` sections; the `omlx` section resolves no
credential at all — so embedding state carries neither a credential value nor a
credential name.

Every `base_url` SHALL be an `http` or `https` API root with a host. URL
username, password, query, and fragment components SHALL be rejected so a
credential cannot be persisted through the URL. A path already ending in
`/embeddings` SHALL be rejected; the client normalizes a trailing slash and
appends that route itself.

Credentials SHALL be resolved from the credential store when `get_embedder()`
constructs a snapshot, and from nowhere else. A missing credential SHALL NOT
prevent process startup. Because the store is read at snapshot time from the
shared state volume, a credential saved in the dashboard SHALL apply to the next
item without restarting a host process or recreating a Compose service.

#### Scenario: secret-bearing URL is rejected

- **WHEN** any embedding base URL contains userinfo or an API key in its query
- **THEN** validation rejects the state and no value is written

#### Scenario: environment variable name is stored, not its value

- **WHEN** any embedding section is saved
- **THEN** the stored object contains neither a credential value nor a
  credential name, because each provider's credential (if any) is located by a
  fixed name

#### Scenario: process environment is read for the next item

- **WHEN** a required credential is saved to the credential store before the
  next `get_embedder()` call
- **THEN** the next snapshot captures it without caching the prior absence, and
  the process environment is not consulted

#### Scenario: editing dotenv requires lifecycle action

- **WHEN** an operator changes a credential or endpoint in `.env` for a running
  scheduler or Compose service
- **THEN** nothing changes, because neither credentials nor embedding endpoints
  resolve from the environment; documentation and diagnostics direct them to the
  settings page instead, and saving there applies to the next item with no
  restart or recreation

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
credential exists in the credential store. An unselected embedder, invalid
embedding state, an incomplete section for the selected provider, or a missing
required credential SHALL each produce a failed check and a non-zero exit.
Doctor SHALL NOT issue an embedding request.

An unselected embedder SHALL be reported distinctly from a configured provider
whose credential or endpoint is missing, and its message SHALL state the
consequence — deduplication is inactive — rather than describing it as an error
in the system.

For OMLX, the API root recorded in embedding state is required and the provider
resolves no credential at all. OpenAI (`RADAR_EMBEDDING_OPENAI_API_KEY`) and
OpenAI-compatible (`EMBEDDING_API_KEY`) credentials are required.

When a credential or endpoint is absent, the message SHALL direct the operator to
the dashboard settings page. It SHALL NOT instruct them to edit `.env`, restart
a host process, or recreate a Compose service, none of which affect resolution.

#### Scenario: nothing selected yet

- **WHEN** no embedder has been selected
- **THEN** doctor reports a failed embedder check stating that no embedder is
  selected and that deduplication is inactive, points at the settings page, and
  exits non-zero

#### Scenario: hosted selection has no key

- **WHEN** OpenAI is selected and `RADAR_EMBEDDING_OPENAI_API_KEY` is absent
  from the store
- **THEN** doctor reports a failed embedder check naming that credential,
  points at the settings page, and exits non-zero

#### Scenario: valid selection is reported without a request

- **WHEN** state and credential are valid
- **THEN** doctor reports the identity successfully and performs no HTTP call

### Requirement: Real profiles supply prefill and every selection is explicit

`configs/models.yaml::embedders` SHALL remain the source of suggested values for
providers with real shipped defaults: `embedders.local` supplies a suggested
OMLX model and `embedders.openai` supplies a suggested OpenAI model. These are
form prefill. They SHALL NOT be applied as runtime defaults, and a section that
has never been saved SHALL NOT inherit them at resolution time.

Every provider section SHALL be complete before its provider can be selected.
No universal endpoint, model, credential, or vector-space id SHALL be invented
for any provider. Selecting a provider whose section is incomplete SHALL raise
`RuntimeError` before any HTTP request.

Because no section inherits a baseline, a partial section SHALL be rejected
rather than silently completed. The backend and Dashboard SHALL derive suggested
values from the same YAML profiles.

#### Scenario: unsaved section does not inherit a baseline

- **WHEN** state selects a provider whose section is missing required fields
- **THEN** resolution raises an actionable `RuntimeError` naming the missing
  fields, rather than filling them from `models.yaml`

#### Scenario: prefill reaches the form, not the pipeline

- **WHEN** an operator opens an unconfigured provider's settings pane
- **THEN** its fields are prefilled from `models.yaml` and nothing is selected
  or persisted until they save

#### Scenario: no provider has a fabricated default

- **WHEN** any provider is selected without a complete saved section
- **THEN** resolution raises before any request

### Requirement: No embedder is selected until an operator selects one

Embedding SHALL have no default provider. An absent `embedding.json`, or a
present one that records no selection, SHALL resolve to an **unselected** state
rather than to any provider.

The capability SHALL expose that state distinctly from a resolution failure, so
a consumer can report "no embedder has been selected" without attempting a
request and without inferring it from an error message. Attempting to resolve a
snapshot while unselected SHALL raise rather than return a degraded embedder.

`configs/models.yaml::embedders` SHALL supply suggested values for a provider an
operator is configuring. It SHALL NOT cause any provider to be selected, and
SHALL NOT determine what runs.

The unselected state is a valid resting state, not a fault. It SHALL NOT prevent
process startup, SHALL NOT abort a running job, and SHALL NOT be repaired by
writing a selection on the operator's behalf.

#### Scenario: fresh install selects nothing

- **WHEN** no `embedding.json` exists
- **THEN** the resolved state is unselected, no provider is chosen, and no
  request is attempted

#### Scenario: unselected is distinguishable from broken

- **WHEN** a consumer asks whether embedding is available and nothing is selected
- **THEN** it learns that no selection exists, separately from any error that a
  configured-but-failing provider would produce

#### Scenario: suggested values do not select a provider

- **WHEN** `configs/models.yaml::embedders` names a local model
- **THEN** that value is available to prefill a form and nothing about it causes
  the local provider to be selected
