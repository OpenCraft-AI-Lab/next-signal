## MODIFIED Requirements

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
