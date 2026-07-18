## ADDED Requirements

### Requirement: `search_knowledge` tool

`paca.tools.knowledge.search.search_knowledge(query, topic=None)` SHALL query GBrain and return a JSON-safe list of `{title, path, snippet, score}` results.

#### Scenario: agent retrieves KB snippets

- **WHEN** an agent calls `search_knowledge("Q4 NVDA highlights")`
- **THEN** it receives up to N hits with the snippet field truncated and the path pointing into the wiki tree

### Requirement: Tool registered in registry

The tool SHALL be added to `_IN_TREE_TOOLS` so it can be referenced from any agent YAML.

#### Scenario: knowledge_manager picks up the tool

- **WHEN** the `knowledge_manager` agent YAML lists `tools: [search_knowledge]`
- **THEN** the agent can call the tool at runtime
