## MODIFIED Requirements

### Requirement: Three embedding providers are supported

`ResolvedEmbedder.embed()` SHALL dispatch using the provider captured in its
snapshot:

- `omlx` — POST to the centralized OMLX API root's `/embeddings` route, with
  endpoint and optional key resolved through the centralized OMLX resolver; do
  not send `dimensions`.
- `openai` — POST to `https://api.openai.com/v1/embeddings` with the
  `OPENAI_API_KEY` credential from the credential store, sending
  `dimensions: 1024`.
- `openai_compatible` — append `/embeddings` to the configured API root, use the
  credential the configured `api_key_env` name identifies in the credential
  store, and send `dimensions: 1024`.

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
`space_id`. `api_key_env` stores only a credential *name* validated against
`^[A-Z][A-Z0-9_]{0,63}$`; `space_id` SHALL match
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`.

`base_url` SHALL be an `http` or `https` API root with a host. URL username,
password, query, and fragment components SHALL be rejected so a credential
cannot be persisted through the URL. A path already ending in `/embeddings`
SHALL be rejected; the client normalizes a trailing slash and appends that route
itself.

Credentials SHALL be resolved from the credential store when `get_embedder()`
constructs a snapshot, and from nowhere else. A missing credential SHALL NOT
prevent process startup. Because the store is read at snapshot time from the
shared state volume, a credential saved in the dashboard SHALL apply to the next
item without restarting a host process or recreating a Compose service.

#### Scenario: secret-bearing URL is rejected

- **WHEN** a compatible base URL contains userinfo or an API key in its query
- **THEN** validation rejects the state and no value is written

#### Scenario: environment variable name is stored, not its value

- **WHEN** compatible settings are saved
- **THEN** state contains `api_key_env` and no resolved credential value

#### Scenario: process environment is read for the next item

- **WHEN** the named credential is saved to the credential store before the next
  `get_embedder()` call
- **THEN** the next snapshot captures it without caching the prior absence, and
  the process environment is not consulted

#### Scenario: editing dotenv requires lifecycle action

- **WHEN** an operator changes a credential in `.env` for a running scheduler or
  Compose service
- **THEN** nothing changes, because credentials no longer resolve from `.env`;
  documentation and diagnostics direct them to the settings page instead, and
  saving there applies to the next item with no restart or recreation

### Requirement: Doctor reports the active snapshot configuration

`next-signal doctor` SHALL report the resolved identity and whether its required
credential exists in the credential store. Invalid embedding state or a missing
credential SHALL produce a failed check and a non-zero exit. Doctor SHALL NOT
issue an embedding request.

For OMLX, the configured base URL is required and `OMLX_API_KEY` remains
optional; an absent optional key SHALL NOT fail the embedder check. OpenAI and
OpenAI-compatible credentials are required.

When a credential is absent, the message SHALL direct the operator to set it on
the dashboard settings page. It SHALL NOT instruct them to edit `.env`, restart
a host process, or recreate a Compose service, none of which affect credential
resolution.

#### Scenario: hosted selection has no key

- **WHEN** OpenAI is selected and `OPENAI_API_KEY` is absent from the store
- **THEN** doctor reports a failed embedder check naming the credential, points
  at the settings page, and exits non-zero

#### Scenario: valid selection is reported without a request

- **WHEN** state and credential are valid
- **THEN** doctor reports the identity successfully and performs no HTTP call
