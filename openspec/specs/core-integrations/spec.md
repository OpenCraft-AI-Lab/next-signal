# core-integrations

Provider integrations live under `src/paca/integrations/`, with domain-specific adapters under `src/paca/integrations/<domain>/`. An integration may register agent-facing tools only when the provider capability is intentionally exposed directly; otherwise tools or workflow stages call the adapter.

## Purpose

A failing or unconfigured integration must not bring down the system. Integrations follow a uniform template so a new API can be added without leaking provider details into tools or agents.

## Requirements

### Requirement: API keys read at call time

Each integration SHALL read its API key inside the tool function body (via `paca.integrations._helpers.env(NAME)`), not at module import.

#### Scenario: missing key does not block startup

- **WHEN** `EXAMPLE_API_KEY` is absent from `.env`
- **THEN** `paca serve` still starts; the missing key only surfaces when an agent actually calls a tool from that integration

#### Scenario: missing key fails loud at call time

- **WHEN** an agent invokes a tool whose key is unset
- **THEN** the tool raises `RuntimeError("EXAMPLE_API_KEY is not set")`

### Requirement: HTTP traffic uses the shared client

Integrations SHALL perform outbound HTTP calls through `paca.integrations._helpers.http_client()`, which applies a 30-second timeout. Direct use of `requests` or unwrapped `httpx` is prohibited.

#### Scenario: shared timeout enforced

- **WHEN** an integration calls a slow remote endpoint
- **THEN** the request aborts after 30 seconds rather than hanging the agent

### Requirement: Per-integration registration is isolated

`paca.integrations.register_all()` SHALL load each integration module in a try/except so a failing integration does not prevent others from registering.

#### Scenario: one bad integration does not break the registry

- **WHEN** the `firecrawl` module fails to import
- **THEN** the failure is logged and the remaining integrations still register their tools

### Requirement: Long results are truncated; payloads are JSON-safe

Integration tools SHALL pass long text through `truncate()` and structured payloads through `to_jsonable()` before returning.

#### Scenario: long article does not blow context

- **WHEN** an integration fetches a multi-thousand-word article
- **THEN** the returned value is bounded in size and serializable to JSON
