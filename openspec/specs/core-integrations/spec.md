# core-integrations

Provider integrations live under `src/next_signal/integrations/`, with domain-specific adapters under `src/next_signal/integrations/<domain>/`. An integration may register agent-facing tools only when the provider capability is intentionally exposed directly; otherwise tools or workflow stages call the adapter.

## Purpose

A failing or unconfigured integration must not bring down the system. Integrations follow a uniform template so a new API can be added without leaking provider details into tools or agents.
## Requirements
### Requirement: API keys read at call time

Each integration SHALL read its API key from the credential store inside the
tool function body, not at module import. `next_signal.integrations._helpers.env(NAME)`
remains the reader for non-credential configuration — executable paths, argv
overrides, and similar deployment settings — and SHALL NOT be used to obtain a
credential.

#### Scenario: missing key does not block startup

- **WHEN** the credential store holds no `EXAMPLE_API_KEY`
- **THEN** `next-signal serve` still starts; the missing credential only surfaces
  when an agent actually calls a tool from that integration

#### Scenario: missing key fails loud at call time

- **WHEN** an agent invokes a tool whose credential is unset
- **THEN** the tool raises `RuntimeError` naming the credential and pointing at
  the settings page

#### Scenario: deployment configuration still comes from the environment

- **WHEN** an integration needs a binary path or argv override
- **THEN** it reads it with `env(NAME)` from the process environment, unchanged

### Requirement: The credential store is folocli's only authentication source

Every `folocli` invocation SHALL require `FOLO_TOKEN` from the credential store
and SHALL raise `RuntimeError` naming the credential and pointing at the settings
page *before* spawning the subprocess when it is absent.

folocli's own cached session file SHALL NOT be treated as a supported
authentication path. It is unreachable in the supported container deployment: no
volume backs its home directory, and the command that populates it completes over
a loopback callback bound inside the container, which a browser on the host
cannot reach. Leaving it as an implicit fallback would also give the system two
sources of truth for one credential, only one of which has a UI.

#### Scenario: absent token fails before the subprocess runs

- **WHEN** a folocli-backed command runs and the store holds no `FOLO_TOKEN`
- **THEN** it raises naming the credential, and no subprocess is spawned

#### Scenario: a cached session does not substitute for the store

- **WHEN** the store holds no `FOLO_TOKEN` but a folocli session file exists
- **THEN** the command still fails, and the session file is not consulted

### Requirement: HTTP traffic uses the shared client

Integrations SHALL perform outbound HTTP calls through `next_signal.integrations._helpers.http_client()`, which applies a 30-second timeout. Direct use of `requests` or unwrapped `httpx` is prohibited.

#### Scenario: shared timeout enforced

- **WHEN** an integration calls a slow remote endpoint
- **THEN** the request aborts after 30 seconds rather than hanging the agent

### Requirement: Per-integration registration is isolated

`next_signal.integrations.register_all()` SHALL load each integration module in a try/except so a failing integration does not prevent others from registering.

#### Scenario: one bad integration does not break the registry

- **WHEN** a module listed in `next_signal.integrations._MODULES` fails to import
- **THEN** the failure is logged and the remaining integrations still register their tools

`_MODULES` is currently an empty list in this repo — the shared cloud-API adapters from the original project (`firecrawl`, `tavily`, `exa`, `notion`, `github`, `slack`, `news`, `weather`, `google_calendar`, `gmail`) were dropped in the trim, since they only served the personal-assistant/Discord front door that isn't part of this repo's scope. The try/except isolation mechanism itself is unaffected — it applies to whatever modules are listed whenever one is added back.

### Requirement: Long results are truncated; payloads are JSON-safe

Integration tools SHALL pass long text through `truncate()` and structured payloads through `to_jsonable()` before returning.

#### Scenario: long article does not blow context

- **WHEN** an integration fetches a multi-thousand-word article
- **THEN** the returned value is bounded in size and serializable to JSON

