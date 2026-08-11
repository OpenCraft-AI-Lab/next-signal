## MODIFIED Requirements

### Requirement: `search_knowledge` tool

`next_signal.tools.knowledge.search.search_knowledge(query, topic=None)` SHALL query GBrain and return a JSON-safe list of `{title, path, snippet, score}` results.

#### Scenario: agent retrieves KB snippets

- **WHEN** an agent calls `search_knowledge("Q4 NVDA highlights")`
- **THEN** it receives up to N hits with the snippet field truncated and the path pointing into the wiki tree

### Requirement: Tool registered in registry

The tool SHALL be registered by the `src/next_signal/tools/knowledge/` package so it can be referenced from any agent YAML.

#### Scenario: an agent picks up the tool

- **WHEN** an agent YAML lists `tools: [search_knowledge]`
- **THEN** the agent can call the tool at runtime

Note: no agent in this repo currently lists `search_knowledge` in its `tools:` (there is no `knowledge_manager` agent) — the registration mechanism itself is real and verified (`src/next_signal/tools/knowledge/__init__.py::register`), just not yet exercised by a shipped agent.
