# core-cli

The `paca` CLI is the operator entry point. All commands run via `uv run paca …`.

## Purpose

Operator tasks (listing components, starting the server, running an agent once, self-checking) must be reachable without scripting against the AgentOS HTTP API.
## Requirements
### Requirement: `paca list` enumerates configured runnables

`paca list` SHALL print configured agents, workflows, and teams by name.

#### Scenario: operator audits available runnables

- **WHEN** the operator runs `paca list`
- **THEN** the output includes `Agents:`, `Workflows:`, and `Teams:` sections with one line per configured runnable

### Requirement: `paca serve` starts AgentOS

`paca serve` SHALL launch the FastAPI AgentOS app on port 7777.

#### Scenario: server is reachable after start

- **WHEN** the operator runs `paca serve`
- **THEN** `http://localhost:7777/docs` returns the OpenAPI page

### Requirement: `paca run-agent` executes a single prompt

`paca run-agent <name> "<prompt>"` SHALL build the named agent (without starting AgentOS) and stream the response to stdout.

#### Scenario: one-shot invocation

- **WHEN** the operator runs `paca run-agent echo "hello"`
- **THEN** the CLI prints the agent's response and exits 0 without binding port 7777

### Requirement: `paca doctor` self-checks the environment

`paca doctor` SHALL verify `.env` configuration, OMLX endpoint reachability, Postgres reachability, the presence of every registered tool, the GBrain CLI / service health, and the folocli authentication (`FOLO_TOKEN` set and `folocli whoami` returns `ok: true`), reporting each check as ✓ or ✗.

#### Scenario: missing key reported

- **WHEN** `ANTHROPIC_API_KEY` is unset
- **THEN** `paca doctor` reports a ✗ for the corresponding check and exits non-zero

#### Scenario: GBrain CLI absent

- **WHEN** the `gbrain` CLI is not on PATH
- **THEN** `paca doctor` reports a ✗ for the GBrain check and explains how to install it

#### Scenario: folocli not authenticated

- **WHEN** `FOLO_TOKEN` is unset and `folocli whoami` returns `ok: false`
- **THEN** `paca doctor` reports a ✗ for the folocli check and points to `folo login` or `FOLO_TOKEN`

### Requirement: `paca info-radar pull` invokes the collector

`paca info-radar pull [--source NAME]` SHALL load `configs/info_radar/sources.yaml`, run every enabled source (or only the named one), persist results to `radar_items`, and print a per-source summary. Exit code is zero unless every enabled source fails.

#### Scenario: operator pulls all sources

- **WHEN** the operator runs `paca info-radar pull`
- **THEN** the CLI invokes each enabled source's CLI, writes new items, and prints one line per source with the count written

#### Scenario: operator pulls one source

- **WHEN** the operator runs `paca info-radar pull --source folo_articles_ai`
- **THEN** the CLI invokes only that source and ignores others

### Requirement: `paca info-radar sweep` deletes expired rows

`paca info-radar sweep` SHALL run the 30-day retention `DELETE` against `radar_items` and report the number of rows removed.

#### Scenario: standalone sweep

- **WHEN** the operator runs `paca info-radar sweep`
- **THEN** the CLI prints the rows-removed count and exits zero, even if no rows were eligible

