## MODIFIED Requirements

### Requirement: API keys read at call time

Each integration SHALL read its API key inside the tool function body (via `next_signal.integrations._helpers.env(NAME)`), not at module import.

#### Scenario: missing key does not block startup

- **WHEN** `EXAMPLE_API_KEY` is absent from `.env`
- **THEN** `next-signal serve` still starts; the missing key only surfaces when an agent actually calls a tool from that integration

#### Scenario: missing key fails loud at call time

- **WHEN** an agent invokes a tool whose key is unset
- **THEN** the tool raises `RuntimeError("EXAMPLE_API_KEY is not set")`

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
