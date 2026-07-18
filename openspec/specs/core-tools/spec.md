# core-tools

Explicit tool registry. Agents reference tools by name in YAML; the registry resolves names to callables.

## Purpose

Avoid dynamic scanning. Every tool the LLM can call is registered explicitly so the available surface is auditable and grep-able.

## Requirements

### Requirement: Tools registered explicitly

`paca.registry` SHALL expose every agent-facing tool through either the `_IN_TREE_TOOLS` mapping, a `src/paca/tools/<domain>/register()` hook, a configured workflow-tool exposure, or an integration `register()` hook. Dynamic scanning is prohibited.

#### Scenario: agent references a registered tool

- **WHEN** an agent YAML lists `tools: [browser_research]`
- **THEN** the registry returns the `browser_research` callable; an unregistered name raises a clear error

#### Scenario: domain tool package registers tools

- **WHEN** an agent YAML lists `tools: [portfolio_list]`
- **THEN** the registry resolves it through `src/paca/tools/finance/__init__.py::register`

#### Scenario: workflow tool exposure registers tools

- **WHEN** `configs/workflows/knowledge_ingest.yaml` enables `expose.tool.name: knowledge_ingest_workflow`
- **THEN** the registry returns a `WorkflowTools` toolkit for that workflow

### Requirement: Provider-prefixed tool names

Provider-backed or integration-specific tools SHALL be named with the form `<provider>_<verb>` (e.g. `tavily_search`, `finnhub_fetch_news`).

#### Scenario: name disambiguates source

- **WHEN** two integrations both expose a "search" capability
- **THEN** their registered names (`tavily_search`, `moomoo_news_search`) prevent the LLM from confusing them at routing time

### Requirement: JSON repair for local models

`paca.tools._json_extract` SHALL repair Qwen3-style malformed JSON tool-call output (trailing commas, single quotes, comment fragments, etc.) using the documented case set.

#### Scenario: regression tests guard the JSON repair

- **WHEN** `paca.tools._json_extract` is modified
- **THEN** the 12-case test suite in `tests/test_json_extract.py` MUST be re-run and must pass before the change ships
