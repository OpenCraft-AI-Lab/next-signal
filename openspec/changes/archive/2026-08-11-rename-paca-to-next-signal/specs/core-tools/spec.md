## MODIFIED Requirements

### Requirement: Tools registered explicitly

`next_signal.registry` SHALL expose every agent-facing tool through either the `_IN_TREE_TOOLS` mapping, a `src/next_signal/tools/<domain>/register()` hook, a configured workflow-tool exposure, or an integration `register()` hook. Dynamic scanning is prohibited.

#### Scenario: agent references a registered tool

- **WHEN** an agent YAML lists `tools: [search_knowledge]`
- **THEN** the registry returns the `search_knowledge` callable; an unregistered name raises a clear error

#### Scenario: domain tool package registers tools

- **WHEN** an agent YAML lists `tools: [search_knowledge]`
- **THEN** the registry resolves it through `src/next_signal/tools/knowledge/__init__.py::register`

#### Scenario: workflow tool exposure registers tools

- **WHEN** `configs/workflows/knowledge_ingest.yaml` enables `expose.tool.name: knowledge_ingest_workflow`
- **THEN** the registry returns a `WorkflowTools` toolkit for that workflow

### Requirement: JSON extraction salvages malformed tool-call wrapping

`next_signal.tools._json_extract.extract_json_object` SHALL salvage the largest balanced `{...}` object out of text that wraps JSON in prose, `<thinking>`/`<action>`-style tags, or markdown code fences, returning the original text unchanged if no candidate object is found. It does **not** repair malformed JSON syntax (trailing commas, unescaped quotes, etc.) — it only extracts a well-formed span from surrounding noise.

Actual repair of malformed-but-almost-valid JSON (trailing commas, unescaped quotes in long strings, comments) happens one layer up, in `next_signal.agents.structured.run_structured`: after extraction, a strict `json.loads`/`model_validate_json` attempt is followed by a `json5.loads()` fallback that tolerates these xgrammar-style near-misses; if both fail, the agent is re-prompted with the validation error and retried up to `max_repairs` times before raising `RuntimeError`.

#### Scenario: regression tests guard the JSON extraction

- **WHEN** `next_signal.tools._json_extract` is modified
- **THEN** the test suite in `tests/test_json_extract.py` MUST be re-run and must pass before the change ships

#### Scenario: xgrammar near-miss is repaired without a retry round-trip

- **WHEN** a local model's structured output has a trailing comma or an unescaped quote inside a long string
- **THEN** `run_structured`'s `json5.loads()` fallback parses it successfully, skipping the repair-prompt retry entirely
